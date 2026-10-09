from typing import Any

from pydantic import BaseModel, JsonValue, TypeAdapter

_json_payload: TypeAdapter[JsonValue] = TypeAdapter(JsonValue)


def _sanitize_for_json(data: Any) -> JsonValue:
    """Serialize declared data; reject opaque runtime objects instead of stringifying."""

    def convert(value: Any) -> Any:
        if isinstance(value, BaseModel):
            return value.model_dump(mode="json")
        if isinstance(value, dict):
            return {key: convert(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [convert(item) for item in value]
        return value

    return _json_payload.validate_python(convert(data), strict=True)


async def broadcast_event(app_context: Any, event_name: str, event_data: dict):
    """Helper to broadcast event to websockets asynchronously."""
    if not app_context or not hasattr(app_context, "connection_manager"):
        return

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
        "topic": f"event:{event_name}",
        "data": sanitized_data,
    }
    await connection_manager.broadcast_to_topic(f"event:{event_name}", message)
