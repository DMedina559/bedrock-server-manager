# bedrock_server_manager/plugins/event_trigger.py
"""
Provides a decorator for triggering plugin events and broadcasting them.
"""

import asyncio
import functools
import inspect
from typing import Callable, Optional, Any, Dict
import logging

logger = logging.getLogger(__name__)


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


def trigger_plugin_event(
    _func: Optional[Callable] = None,
    *,
    before: Optional[str] = None,
    after: Optional[str] = None,
):
    """
    A decorator to trigger plugin events and broadcast them to WebSockets.
    """

    def decorator(func: Callable) -> Callable:
        sig = inspect.signature(func)

        def get_event_kwargs(*args: Any, **kwargs: Any) -> dict:
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
            return dict(bound_args.arguments)

        def _broadcast_event(app_context, event_name, event_data):
            """Helper to broadcast event to websockets."""
            if not app_context or not hasattr(app_context, "connection_manager"):
                return

            connection_manager = app_context.connection_manager
            sanitized_data = _sanitize_for_json(event_data)

            # Remove sensitive or unnecessary data before broadcasting
            if "app_context" in sanitized_data:
                del sanitized_data["app_context"]
            if "current_user" in sanitized_data:
                # You might want to keep the username, but remove the full object
                sanitized_data["current_user"] = str(sanitized_data["current_user"])

            message = {
                "type": "event",
                "topic": f"event:{event_name}",
                "data": sanitized_data,
            }

            if app_context.loop and app_context.loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    connection_manager.broadcast_to_topic(
                        f"event:{event_name}", message
                    ),
                    app_context.loop,
                )

        async def _async_broadcast_event(app_context, event_name, event_data):
            """Async helper to broadcast event to websockets."""
            if not app_context or not hasattr(app_context, "connection_manager"):
                return

            connection_manager = app_context.connection_manager
            sanitized_data = _sanitize_for_json(event_data)

            # Remove sensitive or unnecessary data before broadcasting
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

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            event_kwargs = get_event_kwargs(*args, **kwargs)
            app_context = event_kwargs.get("app_context")

            if before:
                app_context.plugin_manager.trigger_event(before, **event_kwargs)
                _broadcast_event(app_context, before, event_kwargs)

            result = func(*args, **kwargs)

            if after:
                event_kwargs["result"] = result
                app_context.plugin_manager.trigger_event(after, **event_kwargs)
                _broadcast_event(app_context, after, event_kwargs)

            return result

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            event_kwargs = get_event_kwargs(*args, **kwargs)
            app_context = event_kwargs.get("app_context")

            if before:
                app_context.plugin_manager.trigger_event(before, **event_kwargs)
                await _async_broadcast_event(app_context, before, event_kwargs)

            result = await func(*args, **kwargs)

            if after:
                event_kwargs["result"] = result
                app_context.plugin_manager.trigger_event(after, **event_kwargs)
                await _async_broadcast_event(app_context, after, event_kwargs)

            return result

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return wrapper

    if _func is None:
        return decorator
    else:
        return decorator(_func)
