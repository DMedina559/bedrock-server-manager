# bedrock_server_manager/web/websocket_manager.py
import json
import logging
import uuid
from dataclasses import dataclass
from typing import Dict, List, Any

from fastapi import WebSocket

from bedrock_server_manager.web.auth_utils import User

logger = logging.getLogger(__name__)


@dataclass
class Client:
    """Represents a connected WebSocket client."""

    id: str
    user: User
    websocket: WebSocket


class ConnectionManager:
    """Manages WebSocket connections and topic-based subscriptions."""

    def __init__(self):
        # Maps a unique client ID to its Client object
        self.active_connections: Dict[str, Client] = {}
        # Maps a topic to a list of client IDs subscribed to it
        self.subscriptions: Dict[str, List[str]] = {}

    async def connect(self, websocket: WebSocket, user: User) -> str:
        """Accepts a new WebSocket connection, tracks it, and returns the client ID."""
        await websocket.accept()
        client_id = f"{user.username}:{uuid.uuid4()}"
        client = Client(id=client_id, user=user, websocket=websocket)
        self.active_connections[client_id] = client
        logger.info(f"New client connected: {client_id} for user '{user.username}'")
        return client_id

    def disconnect(self, client_id: str):
        """Removes a client's connection and all their subscriptions."""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            # Remove the client from all subscription lists
            for client_ids in self.subscriptions.values():
                if client_id in client_ids:
                    client_ids.remove(client_id)
            logger.info(f"Client disconnected: {client_id}")

    def subscribe(self, client_id: str, topic: str):
        """Subscribes a client to a given topic."""
        if topic not in self.subscriptions:
            self.subscriptions[topic] = []
        if client_id not in self.subscriptions[topic]:
            self.subscriptions[topic].append(client_id)
        logger.info(f"Client {client_id} subscribed to topic '{topic}'")

    def unsubscribe(self, client_id: str, topic: str):
        """Unsubscribes a client from a given topic."""
        if topic in self.subscriptions and client_id in self.subscriptions[topic]:
            self.subscriptions[topic].remove(client_id)
            logger.info(f"Client {client_id} unsubscribed from topic '{topic}'")

    async def send_to_client(self, data: Any, client_id: str):
        """Sends a JSON message to a single client."""
        if client_id in self.active_connections:
            client = self.active_connections[client_id]
            try:
                logger.debug(f"Sending data to client {client_id}: {data}")
                await client.websocket.send_text(json.dumps(data))
            except Exception as e:
                logger.error(f"Failed to send message to client {client_id}: {e}")
                # Consider the connection lost and disconnect the client
                self.disconnect(client_id)

    async def broadcast_to_topic(self, topic: str, data: Any):
        """Broadcasts a JSON message to all clients subscribed to a topic."""
        if topic in self.subscriptions:
            client_ids = list(self.subscriptions[topic])
            logger.debug(
                f"Broadcasting to topic '{topic}' to {len(client_ids)} client(s). Data: {data}"
            )
            # Create a copy of the list to avoid issues if a client disconnects mid-broadcast
            for client_id in client_ids:
                await self.send_to_client(data, client_id)

    async def send_to_user(self, username: str, data: Any):
        """Sends a JSON message to all active connections for a specific user."""
        client_ids_for_user = [
            client.id
            for client in self.active_connections.values()
            if client.user.username == username
        ]
        logger.debug(
            f"Sending data to user '{username}' ({len(client_ids_for_user)} client(s)). Data: {data}"
        )
        # Find all client_ids for this username
        for client_id in client_ids_for_user:
            await self.send_to_client(data, client_id)
