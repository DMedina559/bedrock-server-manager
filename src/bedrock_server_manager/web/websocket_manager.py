# bedrock_server_manager/web/websocket_manager.py
import asyncio
import json
import logging
import time
import uuid
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from fastapi import WebSocket, WebSocketDisconnect

from ..diagnostics.models import TransportDiagnostics
from ..logging import log_operation_error
from ..results import DeliveryResult
from ..state.models import UserInfoState
from .schemas import UserResponse
from .schemas.websocket import json_payload

logger = logging.getLogger(__name__)


@dataclass
class Client:
    """Represent a connected WebSocket client."""

    id: str
    user: UserResponse
    websocket: WebSocket
    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    pending_sends: int = 0


@dataclass
class DataProvider:
    """Represent a registered topic data provider."""

    handler: Callable[..., Any]
    plugin_name: Optional[str] = None


class ConnectionManager:
    """Manage WebSocket connections, topic-based subscriptions, and data providers."""

    def __init__(
        self,
        user_provider: Callable[[str], UserInfoState | None] | None = None,
        *,
        outbound_queue_limit: int = 64,
        record_failure: Callable[[str, BaseException | None], None] | None = None,
    ) -> None:
        if not 1 <= outbound_queue_limit <= 10000:
            raise ValueError("WebSocket queue limit must be between 1 and 10000")
        self.user_provider = user_provider
        self.outbound_queue_limit = outbound_queue_limit
        self.record_failure = record_failure
        self.pending_sends = 0
        self.active_sends = 0
        self.dropped_messages = 0
        self.high_water_mark = 0
        self.send_timeouts = 0
        self.last_send_at: float | None = None
        self.last_send_duration_ms: float | None = None
        self.disconnects_by_reason: Counter[str] = Counter()
        self._accepting = True
        self.io_timeout = 5.0
        # Maps a unique client ID to its Client object
        self.active_connections: Dict[str, Client] = {}
        self.successful_sends = 0
        self.failed_sends = 0
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
        logger.debug("New client connected: %s for user '%s'", client_id, user.username)
        return client_id

    async def disconnect(self, client_id: str, *, reason: str = "peer_closed"):
        """Remove a client's connection and all their subscriptions."""
        if client_id in self.active_connections:
            self.disconnects_by_reason[reason] += 1
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

            logger.debug("Client disconnected: %s", client_id)

    async def revoke_user(self, username: str) -> None:
        for client in list(self.active_connections.values()):
            if client.user.username == username:
                try:
                    await asyncio.wait_for(
                        client.websocket.close(
                            code=1008, reason="Account authorization changed"
                        ),
                        timeout=self.io_timeout,
                    )
                except Exception:
                    logger.exception("Could not close revoked connection %s", client.id)
                finally:
                    await self.disconnect(client.id, reason="authorization_changed")

    async def refresh_authorization(self, client_id: str) -> bool:
        client = self.active_connections.get(client_id)
        if client is None:
            return False
        if self.user_provider is None:
            return True
        user = self.user_provider(client.user.username)
        if (
            user is None
            or not user.is_active
            or user.id != client.user.id
            or user.role != client.user.role
        ):
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
        logger.debug("Client %s subscribed to topic '%s'", client_id, topic)

    async def unsubscribe(self, client_id: str, topic: str):
        """Unsubscribes a client from a given topic."""
        if topic in self.subscriptions and client_id in self.subscriptions[topic]:
            self.subscriptions[topic].remove(client_id)
            if not self.subscriptions[topic]:
                del self.subscriptions[topic]
            logger.debug("Client %s unsubscribed from topic '%s'", client_id, topic)

    async def shutdown(self):
        """Gracefully disconnects all active WebSocket connections."""
        self._accepting = False
        logger.debug(
            "Shutting down %s active WebSocket connections.",
            len(self.active_connections),
        )

        async def close(client: Client) -> None:
            try:
                await asyncio.wait_for(
                    client.websocket.close(code=1001, reason="Server shutting down"),
                    timeout=self.io_timeout,
                )
            except Exception as error:
                log_operation_error(
                    logger,
                    "Error closing websocket for client %s: %s",
                    client.id,
                    error,
                    error=error,
                )

        await asyncio.gather(
            *(close(client) for client in list(self.active_connections.values()))
        )
        for client_id in list(self.active_connections):
            await self.disconnect(client_id, reason="shutdown")
        self.subscriptions.clear()
        self.data_providers.clear()

    def register_data_provider(
        self, topic: str, handler: Callable[..., Any], plugin_name: Optional[str] = None
    ):
        """Register a data provider handler for a given topic."""
        self.data_providers[topic] = DataProvider(
            handler=handler, plugin_name=plugin_name
        )
        logger.debug(
            "Registered data provider for topic '%s' (plugin: %s)",
            topic,
            plugin_name or "core",
        )

    def unregister_data_provider(self, topic: str) -> bool:
        """Unregisters a data provider for a given topic."""
        if topic in self.data_providers:
            del self.data_providers[topic]
            logger.debug("Unregistered data provider for topic '%s'", topic)
            return True
        return False

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
            logger.debug(
                "Unregistered %s data providers for plugin '%s'",
                len(topics_to_remove),
                plugin_name,
            )

    def get_data_provider(self, topic: str) -> Optional[Callable[..., Any]]:
        """Return the handler function for a topic data provider, if registered."""
        provider = self.data_providers.get(topic)
        return provider.handler if provider else None

    async def publish_ws_event(self, event_name: str, data: Any) -> DeliveryResult:
        """Publishes a custom WebSocket event to subscribers of 'ws_event:{event_name}'."""
        topic = f"ws_event:{event_name}"
        message = {
            "type": "ws_event",
            "event": event_name,
            "topic": topic,
            "data": data,
        }
        return await self.broadcast_to_topic(topic, message)

    def diagnostic_snapshot(self) -> TransportDiagnostics:
        """Expose aggregate pressure and fixed disconnect reasons without client identities."""
        return TransportDiagnostics(
            connected_clients=len(self.active_connections),
            subscriptions=sum(len(clients) for clients in self.subscriptions.values()),
            topics=len(self.subscriptions),
            successful_sends=self.successful_sends,
            failed_sends=self.failed_sends,
            pending_sends=self.pending_sends,
            active_sends=self.active_sends,
            queue_limit_per_client=self.outbound_queue_limit,
            dropped_messages=self.dropped_messages,
            high_water_mark=self.high_water_mark,
            send_timeouts=self.send_timeouts,
            last_send_at=self.last_send_at,
            last_send_duration_ms=self.last_send_duration_ms,
            max_pending_per_client=max(
                (client.pending_sends for client in self.active_connections.values()),
                default=0,
            ),
            disconnects_by_reason=dict(self.disconnects_by_reason),
            accepting=self._accepting,
        )

    async def send_to_client(self, data: Any, client_id: str) -> DeliveryResult:
        """Bound concurrent sends per client and acknowledge only completed delivery."""
        encoded = json.dumps(json_payload(data).value, allow_nan=False)
        if not self._accepting or not await self.refresh_authorization(client_id):
            return DeliveryResult(targeted=1, unavailable=1)
        client = self.active_connections.get(client_id)
        if client is None:
            return DeliveryResult(targeted=1, unavailable=1)
        if client.pending_sends >= self.outbound_queue_limit:
            self.dropped_messages += 1
            if self.record_failure is not None:
                self.record_failure("capacity", None)
            return DeliveryResult(targeted=1, failed=1)
        started = time.monotonic()
        client.pending_sends += 1
        self.pending_sends += 1
        self.high_water_mark = max(self.high_water_mark, client.pending_sends)
        try:
            async with asyncio.timeout(self.io_timeout):
                async with client.send_lock:
                    if not self._accepting or not await self.refresh_authorization(
                        client_id
                    ):
                        return DeliveryResult(targeted=1, unavailable=1)
                    if self.active_connections.get(client_id) is not client:
                        return DeliveryResult(targeted=1, unavailable=1)
                    self.active_sends += 1
                    try:
                        await client.websocket.send_text(encoded)
                    finally:
                        self.active_sends -= 1
            self.successful_sends += 1
            self.last_send_at = time.time()
            return DeliveryResult(targeted=1, sent=1)
        except (WebSocketDisconnect, RuntimeError):
            self.failed_sends += 1
            await self.disconnect(client_id, reason="peer_closed")
            return DeliveryResult(targeted=1, unavailable=1)
        except Exception as error:
            self.failed_sends += 1
            reason = (
                "send_timeout" if isinstance(error, TimeoutError) else "send_failed"
            )
            if isinstance(error, TimeoutError):
                self.send_timeouts += 1
            if self.record_failure is not None:
                self.record_failure(reason, error)
            log_operation_error(logger, "WebSocket delivery failed", error=error)
            await self.disconnect(client_id, reason=reason)
            return DeliveryResult(targeted=1, failed=1)
        finally:
            client.pending_sends -= 1
            self.pending_sends -= 1
            self.last_send_duration_ms = max(0, (time.monotonic() - started) * 1000)

    async def broadcast_to_topic(self, topic: str, data: Any) -> DeliveryResult:
        """Broadcasts a JSON message to all clients subscribed to a topic."""
        clients_to_notify = set()

        if topic in self.subscriptions:
            clients_to_notify.update(self.subscriptions[topic])

        if "*" in self.subscriptions:
            clients_to_notify.update(self.subscriptions["*"])

        # Create a copy of the list to avoid issues if a client disconnects mid-broadcast
        client_ids = list(clients_to_notify)

        coroutines = [self.send_to_client(data, client_id) for client_id in client_ids]
        return (
            DeliveryResult.combine(list(await asyncio.gather(*coroutines)))
            if coroutines
            else DeliveryResult()
        )

    async def send_to_user(self, username: str, data: Any) -> DeliveryResult:
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
        return (
            DeliveryResult.combine(list(await asyncio.gather(*coroutines)))
            if coroutines
            else DeliveryResult()
        )
