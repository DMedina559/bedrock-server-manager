from typing import Callable


def app_event(event_name: str, *, priority: int = 0) -> Callable:
    """Decorator to easily register a plugin method as an event listener for an event.

    .. rubric:: Example

    @app_event("on_load")
    def on_data_updated(self, **kwargs):
        pass"""

    def decorator(func: Callable) -> Callable:
        setattr(func, "_app_event_name", event_name)
        setattr(func, "_app_event_priority", priority)
        return func

    return decorator
