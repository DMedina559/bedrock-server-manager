"""Bounded, transport-independent progress and timing for backup workers."""

import asyncio
import inspect
import logging
import time

from ..utils.progress import report_stage
from ..utils.threads import check_cancellation, run_in_thread

logger = logging.getLogger(__name__)


async def backup_worker(target, *args, **kwargs):
    """Bridge a worker's coarse stages to its existing managed task."""
    loop = asyncio.get_running_loop()

    def stage(message):
        asyncio.run_coroutine_threadsafe(report_stage(message), loop).result()

    if "stage_callback" in inspect.signature(target).parameters:
        kwargs.setdefault("stage_callback", stage)
    started = time.monotonic()
    try:
        return await run_in_thread(target, *args, **kwargs)
    finally:
        logger.debug(
            "Backup worker finished: operation=%s duration_ms=%.3f",
            getattr(target, "__name__", type(target).__name__),
            (time.monotonic() - started) * 1000,
        )


def tree_paths(root, cancellation_event=None):
    """Check cancellation while enumerating large trees, before collecting them."""
    check_cancellation(cancellation_event)
    yield root
    if root.is_dir():
        for path in root.rglob("*"):
            check_cancellation(cancellation_event)
            yield path
