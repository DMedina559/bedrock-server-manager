from typing import Callable, Union


def task_loop(interval: Union[int, float]) -> Callable:
    """Register a periodic plugin task with an interval in seconds.

    The first call follows the initial interval. Sync and async callbacks are
    supported; callback failures are logged and the loop continues.
    """

    def decorator(func: Callable) -> Callable:
        setattr(func, "_task_loop_interval", interval)
        return func

    return decorator
