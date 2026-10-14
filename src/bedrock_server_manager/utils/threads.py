"""Keep synchronous workers owned until their execution actually finishes."""

import asyncio
import inspect
import threading
from typing import Any, Callable, TypeVar

Result = TypeVar("Result")


async def run_in_thread(
    target: Callable[..., Result], *args: Any, **kwargs: Any
) -> Result:
    cancellation_event = threading.Event()
    try:
        if "cancellation_event" in inspect.signature(target).parameters:
            kwargs["cancellation_event"] = cancellation_event
    except (TypeError, ValueError):
        pass
    worker = asyncio.create_task(asyncio.to_thread(target, *args, **kwargs))
    try:
        return await asyncio.shield(worker)
    except asyncio.CancelledError:
        cancellation_event.set()
        while not worker.done():
            try:
                await asyncio.shield(worker)
            except asyncio.CancelledError:
                continue
            except Exception:
                break
        if not worker.cancelled():
            worker.exception()
        raise
