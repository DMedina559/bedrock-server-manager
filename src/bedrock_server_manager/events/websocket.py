"""Optional observer preserving the public WebSocket event protocol."""

from typing import Any, Protocol

from ..results import DeliveryResult
from .bus import EventBus
from .models import EventEnvelope


class TopicPublisher(Protocol):
    async def broadcast_to_topic(
        self, topic: str, message: dict[str, Any]
    ) -> DeliveryResult: ...


def attach_websocket_observer(bus: EventBus, manager: TopicPublisher) -> str:
    async def publish(event: EventEnvelope) -> DeliveryResult:
        data = event.model_dump(
            exclude={"name", "source", "timestamp", "parent_event_id"},
            exclude_none=True,
        )
        return await manager.broadcast_to_topic(
            f"event:{event.name}",
            {"type": "event", "topic": f"event:{event.name}", **data},
        )

    return bus.subscribe("*", publish, owner="transport:websocket", observer=True)
