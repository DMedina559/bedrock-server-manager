from typing import Callable


def app_event(event_name: str) -> Callable:
    """
    Decorator to easily register a plugin method as an event listener for an event.

    Example:
        @app_event("on_load")
        def on_data_updated(self, **kwargs):
            pass
    """

    def decorator(func: Callable) -> Callable:
        setattr(func, "_app_event_name", event_name)
        return func

    return decorator
