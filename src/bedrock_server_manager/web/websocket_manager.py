# bedrock_server_manager/web/websocket_manager.py
import asyncio
import json
import logging
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from fastapi import WebSocket, WebSocketDisconnect

from .schemas import UserResponse
from .schemas.websocket import json_payload
from ..state.models import UserInfoState

logger = logging.getLogger(__name__)


@dataclass
class Client:
    """Represents a connected WebSocket client."""

    id: str
    user: UserResponse
    websocket: WebSocket


@dataclass
class DataProvider:
    """Represents a registered topic data provider."""

    handler: Callable[..., Any]
    plugin_name: Optional[str] = None


class ConnectionManager:
    """Manages WebSocket connections, topic-based subscriptions, and data providers."""

    def __init__(self, user_provider: Callable[[str], UserInfoState | None] | None = None) -> None:
        self.user_provider = user_provider
        # Maps a unique client ID to its Client object
        self.active_connections: Dict[str, Client] = {}
        # Maps a topic to a list of client IDs subscribed to it
        self.subscriptions: Dict[str, List[str]] = {}
        # Maps a topic to a registered DataProvider
        self.data_providers: Dict[str, DataProvider] = {}

    async def connect(self, websocket: WebSocket, user: UserResponse) -> str:
        """Accepts a new WebSocket connection, tracks it, and returns the client ID."""
        # Connection is accepted in the router
        client_id = f"{user.username}:{uuid.uuid4()}"
        client = Client(id=client_id, user=user, websocket=websocket)
        self.active_connections[client_id] = client
        logger.info(f"New client connected: {client_id} for user '{user.username}'")
        return client_id

    async def disconnect(self, client_id: str):
        """Removes a client's connection and all their subscriptions."""
        if client_id in self.active_connections:
            del self.active_connections[client_id]

            # Remove the client from all subscription lists
            empty_topics = []
            for topic, client_ids in self.subscriptions.items():
                if client_id in client_ids:
                    client_ids.remove(client_id)
                if not client_ids:
                    empty_topics.append(topic)

            for topic in empty_topics:
                del self.subscriptions[topic]

            logger.info(f"Client disconnected: {client_id}")

    async def revoke_user(self, username: str) -> None:
        for client in list(self.active_connections.values()):
            if client.user.username == username:
                try:
                    await asyncio.wait_for(client.websocket.close(code=1008, reason="Account authorization changed"), timeout=5)
                except Exception:
                    logger.exception("Could not close revoked connection %s", client.id)
                finally:
                    await self.disconnect(client.id)

    async def refresh_authorization(self, client_id: str) -> bool:
        client = self.active_connections.get(client_id)
        if client is None:
            return False
        if self.user_provider is None:
            return True
        user = self.user_provider(client.user.username)
        if user is None or not user.is_active or user.id != client.user.id or user.role != client.user.role:
            await self.revoke_user(client.user.username)
            return False
        client.user = UserResponse.model_validate(user, from_attributes=True)
        return True

    async def subscribe(self, client_id: str, topic: str):
        """Subscribes a client to a given topic."""
        if topic not in self.subscriptions:
            self.subscriptions[topic] = []
        if client_id not in self.subscriptions[topic]:
            self.subscriptions[topic].append(client_id)
        logger.info(f"Client {client_id} subscribed to topic '{topic}'")

    async def unsubscribe(self, client_id: str, topic: str):
        """Unsubscribes a client from a given topic."""
        if topic in self.subscriptions and client_id in self.subscriptions[topic]:
            self.subscriptions[topic].remove(client_id)
            if not self.subscriptions[topic]:
                del self.subscriptions[topic]
            logger.info(f"Client {client_id} unsubscribed from topic '{topic}'")

    async def shutdown(self):
        """Gracefully disconnects all active WebSocket connections."""
        logger.info(
            f"Shutting down {len(self.active_connections)} active WebSocket connections."
        )
        # Create a copy of the values to avoid RuntimeError: dictionary changed size during iteration
        for client in list(self.active_connections.values()):
            try:
                await client.websocket.close(code=1001, reason="Server shutting down")
            except Exception as e:
                logger.error(f"Error closing websocket for client {client.id}: {e}")
        self.active_connections.clear()
        self.subscriptions.clear()
        self.data_providers.clear()

    def register_data_provider(
        self, topic: str, handler: Callable[..., Any], plugin_name: Optional[str] = None
    ):
        """Registers a data provider handler for a given topic."""
        self.data_providers[topic] = DataProvider(
            handler=handler, plugin_name=plugin_name
        )
        logger.info(
            f"Registered data provider for topic '{topic}' (plugin: {plugin_name or 'core'})"
        )

    def unregister_data_provider(self, topic: str):
        """Unregisters a data provider for a given topic."""
        if topic in self.data_providers:
            del self.data_providers[topic]
            logger.info(f"Unregistered data provider for topic '{topic}'")

    def unregister_plugin_providers(self, plugin_name: str):
        """Unregisters all data providers associated with a specific plugin."""
        topics_to_remove = [
            topic
            for topic, provider in self.data_providers.items()
            if provider.plugin_name == plugin_name
        ]
        for topic in topics_to_remove:
            del self.data_providers[topic]
        if topics_to_remove:
            logger.info(
                f"Unregistered {len(topics_to_remove)} data providers for plugin '{plugin_name}'"
            )

    def get_data_provider(self, topic: str) -> Optional[Callable[..., Any]]:
        """Returns the handler function for a topic data provider, if registered."""
        provider = self.data_providers.get(topic)
        return provider.handler if provider else None

    async def publish_ws_event(self, event_name: str, data: Any):
        """Publishes a custom WebSocket event to subscribers of 'ws_event:{event_name}'."""
        topic = f"ws_event:{event_name}"
        message = {
            "type": "ws_event",
            "event": event_name,
            "topic": topic,
            "data": data,
        }
        await self.broadcast_to_topic(topic, message)

    async def send_to_client(self, data: Any, client_id: str):
        """Sends a JSON message to a single client."""
        encoded = json.dumps(json_payload(data).value, allow_nan=False)
        if not await self.refresh_authorization(client_id):
            return
        if client_id in self.active_connections:
            client = self.active_connections[client_id]
            try:
                await client.websocket.send_text(encoded)
            except (WebSocketDisconnect, RuntimeError) as e:
                # Catch both normal disconnection and the "WebSocket is not connected" RuntimeError
                logger.info(
                    f"Failed to send message to client {client_id} (disconnected): {e}"
                )
                await self.disconnect(client_id)
            except Exception as e:
                logger.error(f"Failed to send message to client {client_id}: {e}")
                # Consider the connection lost and disconnect the client
                await self.disconnect(client_id)

    async def broadcast_to_topic(self, topic: str, data: Any):
        """Broadcasts a JSON message to all clients subscribed to a topic."""
        clients_to_notify = set()

        if topic in self.subscriptions:
            clients_to_notify.update(self.subscriptions[topic])

        if "*" in self.subscriptions:
            clients_to_notify.update(self.subscriptions["*"])

        # Create a copy of the list to avoid issues if a client disconnects mid-broadcast
        client_ids = list(clients_to_notify)

        coroutines = [self.send_to_client(data, client_id) for client_id in client_ids]
        if coroutines:
            await asyncio.gather(*coroutines)

    async def send_to_user(self, username: str, data: Any):
        """Sends a JSON message to all active connections for a specific user."""
        # Find all client_ids for this username
        client_ids_for_user = [
            client.id
            for client in self.active_connections.values()
            if client.user.username == username
        ]

        coroutines = [
            self.send_to_client(data, client_id) for client_id in client_ids_for_user
        ]
        if coroutines:
            await asyncio.gather(*coroutines)
