from typing import Callable, Union


def task_loop(interval: Union[int, float]) -> Callable:
    """
    Decorator to easily register a plugin method as a background task loop.

    The task will execute periodically, waiting for the specified `interval` (in seconds)
    between each execution. The first execution will happen after the initial interval.

    Exceptions within the task are caught and logged, allowing the loop to continue.
    Works with both synchronous and asynchronous functions.

    Example:
        @task_loop(60)
        def my_background_task(self):
            pass

    Args:
        interval (int | float): The time in seconds to wait between executions.
    """

    def decorator(func: Callable) -> Callable:
        setattr(func, "_task_loop_interval", interval)
        return func

    return decorator
