import asyncio
from typing import Any


def _sanitize_for_json(data: Any) -> Any:
    """
    Recursively sanitizes data to make it JSON serializable.
    Converts complex objects to their string representation.
    """
    if isinstance(data, (str, int, float, bool, type(None))):
        return data
    if isinstance(data, dict):
        return {_sanitize_for_json(k): _sanitize_for_json(v) for k, v in data.items()}
    if isinstance(data, (list, tuple)):
        return [_sanitize_for_json(item) for item in data]
    # For any other type, convert to string
    try:
        return str(data)
    except Exception:
        return f"<Unserializable object of type {type(data).__name__}>"


def broadcast_event(app_context: Any, event_name: str, event_data: dict):
    """Helper to broadcast event to websockets."""
    if not app_context or not hasattr(app_context, "connection_manager"):
        return

    connection_manager = app_context.connection_manager
    sanitized_data = _sanitize_for_json(event_data)

    if "app_context" in sanitized_data:
        del sanitized_data["app_context"]
    if "current_user" in sanitized_data:
        sanitized_data["current_user"] = str(sanitized_data["current_user"])

    message = {
        "type": "event",
        "topic": f"event:{event_name}",
        "data": sanitized_data,
    }

    if app_context.loop and app_context.loop.is_running():
        asyncio.run_coroutine_threadsafe(
            connection_manager.broadcast_to_topic(f"event:{event_name}", message),
            app_context.loop,
        )


async def async_broadcast_event(app_context: Any, event_name: str, event_data: dict):
    """Async helper to broadcast event to websockets."""
    if not app_context or not hasattr(app_context, "connection_manager"):
        return

    connection_manager = app_context.connection_manager
    sanitized_data = _sanitize_for_json(event_data)

    if "app_context" in sanitized_data:
        del sanitized_data["app_context"]
    if "current_user" in sanitized_data:
        sanitized_data["current_user"] = str(sanitized_data["current_user"])

    message = {
        "type": "event",
        "topic": f"event:{event_name}",
        "data": sanitized_data,
    }
    await connection_manager.broadcast_to_topic(f"event:{event_name}", message)
