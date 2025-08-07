# bedrock_server_manager/plugins/event_trigger.py
"""
Provides a decorator for triggering plugin events.
"""

import functools
import inspect
from typing import Callable, Optional, Any

from ..instances import get_plugin_manager_instance


def trigger_plugin_event(
    _func: Optional[Callable] = None,
    *,
    before: Optional[str] = None,
    after: Optional[str] = None,
):
    """
    A decorator to trigger plugin events before and after a function call.

    This decorator can be used to decouple API functions from the plugin manager.
    It fetches the global plugin manager instance and uses it to trigger events.

    Can be used with or without arguments:
    @trigger_plugin_event(before="before_event", after="after_event")
    def my_function(server_name: str):
        ...

    The arguments of the decorated function will be passed as keyword arguments
    to the event.

    Args:
        before (Optional[str]): The name of the event to trigger before the
                                decorated function is called.
        after (Optional[str]): The name of the event to trigger after the
                               decorated function is called. The result of the
                               decorated function will be passed as the 'result'
                               keyword argument to the event.
    """

    def decorator(func: Callable) -> Callable:
        sig = inspect.signature(func)

        def get_event_kwargs(*args: Any, **kwargs: Any) -> dict:
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
            return dict(bound_args.arguments)

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            plugin_manager = get_plugin_manager_instance()
            event_kwargs = get_event_kwargs(*args, **kwargs)

            if before:
                plugin_manager.trigger_event(before, **event_kwargs)

            result = func(*args, **kwargs)

            if after:
                event_kwargs["result"] = result
                plugin_manager.trigger_event(after, **event_kwargs)

            return result

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            plugin_manager = get_plugin_manager_instance()
            event_kwargs = get_event_kwargs(*args, **kwargs)

            if before:
                plugin_manager.trigger_event(before, **event_kwargs)

            result = await func(*args, **kwargs)

            if after:
                event_kwargs["result"] = result
                plugin_manager.trigger_event(after, **event_kwargs)

            return result

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return wrapper

    if _func is None:
        return decorator
    else:
        return decorator(_func)
