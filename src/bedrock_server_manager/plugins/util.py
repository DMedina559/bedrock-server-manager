from typing import Any

from ..events.serialization import sanitize as _sanitize_for_json
from ..state_revision import RevisionStamp, revision_clock


async def broadcast_event(
    app_context: Any,
    event_name: str,
    event_data: dict,
    *,
    revision: RevisionStamp | None = None,
):
    """Helper to broadcast event to websockets asynchronously."""
    if not app_context or not hasattr(app_context, "connection_manager"):
        return

    revision = revision if revision is not None else revision_clock.capture()
    connection_manager = app_context.connection_manager
    public_data = {
        key: value
        for key, value in event_data.items()
        if key
        not in {
            "app_context",
            "current_user",
            "event",
            "_triggering_plugin",
        }
    }
    sanitized_data = _sanitize_for_json(public_data)

    message = {
        "type": "event",
        **revision,
        "topic": f"event:{event_name}",
        "data": sanitized_data,
    }
    await connection_manager.broadcast_to_topic(f"event:{event_name}", message)
