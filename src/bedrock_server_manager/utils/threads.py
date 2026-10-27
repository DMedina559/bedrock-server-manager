"""Keep synchronous workers owned until their execution actually finishes."""

import asyncio
import inspect
import logging
import threading
import time
from dataclasses import dataclass
from typing import IO, Any, Callable, TypedDict, TypeVar

Result = TypeVar("Result")
logger = logging.getLogger(__name__)


@dataclass
class _Worker:
    submitted_at: float
    started_at: float | None = None
    cancelled_at: float | None = None


_workers: dict[asyncio.Task, _Worker] = {}


class WorkerSnapshot(TypedDict):
    running: int
    queued: int
    draining: int
    oldest_draining_seconds: float | None


def check_cancellation(cancellation_event: threading.Event | None) -> None:
    """Stop a cooperative worker before its next unit of filesystem work."""
    if cancellation_event is not None and cancellation_event.is_set():
        raise InterruptedError("Worker cancellation requested.")


def copy_stream(
    source: IO[bytes],
    target: IO[bytes],
    cancellation_event: threading.Event | None = None,
) -> None:
    """Copy in bounded chunks and check cancellation between reads and writes."""
    while True:
        check_cancellation(cancellation_event)
        chunk = source.read(1024 * 1024)
        if not chunk:
            break
        check_cancellation(cancellation_event)
        target.write(chunk)


def worker_snapshot() -> WorkerSnapshot:
    """Return metadata-only pressure for workers owned by the current loop."""
    loop = asyncio.get_running_loop()
    workers = [
        record for task, record in _workers.copy().items() if task.get_loop() is loop
    ]
    draining = [record for record in workers if record.cancelled_at is not None]
    return {
        "running": sum(record.started_at is not None for record in workers),
        "queued": sum(record.started_at is None for record in workers),
        "draining": len(draining),
        "oldest_draining_seconds": max(
            (
                max(0, time.monotonic() - record.cancelled_at)
                for record in draining
                if record.cancelled_at is not None
            ),
            default=None,
        ),
    }


async def run_in_thread(
    target: Callable[..., Result], *args: Any, **kwargs: Any
) -> Result:
    cancellation_event = threading.Event()
    try:
        signature = inspect.signature(target)
        parameter = signature.parameters.get("cancellation_event")
        if (
            parameter is not None
            and parameter.kind != inspect.Parameter.POSITIONAL_ONLY
        ):
            supplied = signature.bind_partial(*args, **kwargs).arguments
            if "cancellation_event" not in supplied:
                kwargs["cancellation_event"] = cancellation_event
            elif isinstance(supplied["cancellation_event"], threading.Event):
                cancellation_event = supplied["cancellation_event"]
    except (TypeError, ValueError):
        pass
    record = _Worker(submitted_at=time.monotonic())
    worker_name = getattr(target, "__qualname__", type(target).__name__)

    def invoke() -> Result:
        record.started_at = time.monotonic()
        return target(*args, **kwargs)

    worker = asyncio.create_task(asyncio.to_thread(invoke))
    _workers[worker] = record
    worker.add_done_callback(lambda task: _workers.pop(task, None))
    try:
        return await asyncio.shield(worker)
    except asyncio.CancelledError:
        record.cancelled_at = time.monotonic()
        cancellation_event.set()
        logger.warning(
            "Worker cancellation requested: %s; waiting for worker to stop",
            worker_name,
        )
        while not worker.done():
            try:
                await asyncio.shield(worker)
            except asyncio.CancelledError:
                continue
            except Exception:
                break
        if not worker.cancelled():
            error = worker.exception()
            if error is not None and not isinstance(error, InterruptedError):
                logger.warning(
                    "Worker failed while draining after cancellation: %s",
                    worker_name,
                    exc_info=(type(error), error, error.__traceback__),
                )
        logger.debug(
            "Worker drained after cancellation: %s (%.3f seconds)",
            worker_name,
            time.monotonic() - record.cancelled_at,
        )
        raise
