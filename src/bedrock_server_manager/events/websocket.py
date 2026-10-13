"""Optional observer preserving the public WebSocket event protocol."""

from typing import Any

from .bus import EventBus
from .models import EventEnvelope


def attach_websocket_observer(bus: EventBus, manager: Any) -> str:
    async def publish(event: EventEnvelope) -> Any:
        data = event.model_dump(
            exclude={"name", "source", "timestamp", "parent_event_id"},
            exclude_none=True,
        )
        return await manager.broadcast_to_topic(
            f"event:{event.name}",
            {"type": "event", "topic": f"event:{event.name}", **data},
        )

    return bus.subscribe("*", publish, owner="transport:websocket", observer=True)
