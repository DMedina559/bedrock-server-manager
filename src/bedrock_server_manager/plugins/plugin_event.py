from typing import Callable


def plugin_event(event_name: str) -> Callable:
    """
    Decorator to easily register a plugin method as an event listener for a custom event.

    Example:
        @plugin_event("myplugin:data_updated")
        def on_data_updated(self, **kwargs):
            pass
    """

    def decorator(func: Callable) -> Callable:
        setattr(func, "_plugin_event_name", event_name)
        return func

    return decorator
