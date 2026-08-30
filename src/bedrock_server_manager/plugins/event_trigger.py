# bedrock_server_manager/plugins/event_trigger.py
"""
Provides a decorator for triggering plugin events and broadcasting them.
"""

import functools
import inspect
import logging
from typing import (
    Any,
    Awaitable,
    Callable,
    Optional,
    ParamSpec,
    TypeVar,
    cast,
    overload,
)

from .util import async_broadcast_event, broadcast_event

logger = logging.getLogger(__name__)


P = ParamSpec("P")
R = TypeVar("R")


@overload
def trigger_app_event(
    _func: Callable[P, R],
) -> Callable[P, R]: ...


@overload
def trigger_app_event(
    _func: None = None,
    *,
    before: Optional[str] = None,
    after: Optional[str] = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]: ...


def trigger_app_event(  # noqa: C901
    _func: Optional[Callable[P, R]] = None,
    *,
    before: Optional[str] = None,
    after: Optional[str] = None,
) -> Callable[[Callable[P, R]], Callable[P, R]] | Callable[P, R]:
    """
    A decorator to trigger plugin events and broadcast them to WebSockets.
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        sig = inspect.signature(func)

        def get_event_kwargs(*args: Any, **kwargs: Any) -> dict:
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
            return dict(bound_args.arguments)

        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            event_kwargs = get_event_kwargs(*args, **kwargs)
            app_context = event_kwargs.get("app_context")

            if before and app_context:
                app_context.plugin_manager.trigger_event(before, **event_kwargs)
                broadcast_event(app_context, before, event_kwargs)

            result = func(*args, **kwargs)

            if after and app_context:
                event_kwargs["result"] = result
                app_context.plugin_manager.trigger_event(after, **event_kwargs)
                broadcast_event(app_context, after, event_kwargs)

            return result

        @functools.wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            event_kwargs = get_event_kwargs(*args, **kwargs)
            app_context = event_kwargs.get("app_context")

            if before and app_context:
                if hasattr(app_context.plugin_manager, "trigger_event_async"):
                    await app_context.plugin_manager.trigger_event_async(
                        before, **event_kwargs
                    )
                else:
                    app_context.plugin_manager.trigger_event(before, **event_kwargs)
                await async_broadcast_event(app_context, before, event_kwargs)

            result = await cast(Awaitable[R], func(*args, **kwargs))

            if after and app_context:
                event_kwargs["result"] = result
                if hasattr(app_context.plugin_manager, "trigger_event_async"):
                    await app_context.plugin_manager.trigger_event_async(
                        after, **event_kwargs
                    )
                else:
                    app_context.plugin_manager.trigger_event(after, **event_kwargs)
                await async_broadcast_event(app_context, after, event_kwargs)

            return result

        if inspect.iscoroutinefunction(func):
            return async_wrapper  # type: ignore[return-value]
        else:
            return wrapper

    if _func is None:
        return decorator
    else:
        return decorator(_func)
