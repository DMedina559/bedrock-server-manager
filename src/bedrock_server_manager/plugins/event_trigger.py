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
    Dict,
    Optional,
    ParamSpec,
    Tuple,
    TypeVar,
    cast,
    overload,
)

from .cancellable_event import CancellableEvent
from .util import broadcast_event

logger = logging.getLogger(__name__)

# Global registry for event identity keys
_event_registry: Dict[str, Tuple[str, ...]] = {}


P = ParamSpec("P")
R = TypeVar("R")


@overload
def trigger_event(
    _func: Callable[P, Awaitable[R]],
) -> Callable[P, Awaitable[R]]: ...


@overload
def trigger_event(
    _func: None = None,
    *,
    before: Optional[str] = None,
    after: Optional[str] = None,
    identity_keys: Optional[Tuple[str, ...]] = None,
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]: ...


def trigger_event(
    _func: Optional[Callable[P, Awaitable[R]]] = None,
    *,
    before: Optional[str] = None,
    after: Optional[str] = None,
    identity_keys: Optional[Tuple[str, ...]] = None,
) -> (
    Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]
    | Callable[P, Awaitable[R]]
):
    """
    A decorator to trigger plugin events and broadcast them to WebSockets.
    Because the application core is async, the decorated function must be async.
    """

    if identity_keys is not None:
        if before:
            _event_registry[before] = identity_keys
        if after:
            _event_registry[after] = identity_keys

    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        sig = inspect.signature(func)

        def get_event_kwargs(*args: Any, **kwargs: Any) -> dict:
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
            return dict(bound_args.arguments)

        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            event_kwargs = get_event_kwargs(*args, **kwargs)
            app_context = event_kwargs.get("app_context")
            cancellable_event = CancellableEvent()
            event_kwargs["event"] = cancellable_event

            if before and app_context:
                plugin_kwargs = dict(event_kwargs)
                plugin_kwargs.pop("app_context", None)
                await app_context.plugin_manager.trigger_event(before, **plugin_kwargs)
                await broadcast_event(app_context, before, event_kwargs)
                if cancellable_event.is_cancelled:
                    return cast(
                        R,
                        {
                            "status": "canceled",
                            "message": cancellable_event.cancel_reason
                            or "Canceled by plugin",
                        },
                    )

            result = await cast(Awaitable[R], func(*args, **kwargs))

            if after and app_context:
                event_kwargs["result"] = result
                plugin_kwargs = dict(event_kwargs)
                plugin_kwargs.pop("app_context", None)
                await app_context.plugin_manager.trigger_event(after, **plugin_kwargs)
                await broadcast_event(app_context, after, event_kwargs)

            return result

        return wrapper

    if _func is None:
        return decorator
    else:
        return decorator(_func)
