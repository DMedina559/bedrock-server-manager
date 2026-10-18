from typing import Callable

from ..events.models import EventFilter


def app_event(
    event_name: str,
    *,
    priority: int = 0,
    filters: EventFilter | None = None,
    listener_id: str | None = None,
    before: tuple[str, ...] = (),
    after: tuple[str, ...] = (),
) -> Callable:
    """Decorator to easily register a plugin method as an event listener for an event.

    .. rubric:: Example

    @app_event("on_load")
    def on_data_updated(self, **kwargs):
        pass"""

    def decorator(func: Callable) -> Callable:
        setattr(func, "_app_event_name", event_name)
        setattr(func, "_app_event_priority", priority)
        setattr(
            func,
            "_app_event_options",
            dict(filters=filters, listener_id=listener_id, before=before, after=after),
        )
        return func

    return decorator
