"""Bounded, transport-independent progress and timing for backup workers."""

import asyncio
import inspect
import logging
import time
from collections import defaultdict
from contextlib import contextmanager

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


class FileWork:
    """Aggregate filesystem timings and throttle metadata-only progress updates."""

    def __init__(self, operation, stage_callback=None):
        self.operation = operation
        self.stage_callback = stage_callback
        self.started = time.perf_counter()
        self._clock = time.monotonic
        self.last_progress = self._clock()
        self.timings = defaultdict(float)
        self.files = 0
        self.bytes = 0

    @contextmanager
    def phase(self, name):
        started = time.perf_counter()
        try:
            yield
        finally:
            self.timings[name] += time.perf_counter() - started

    def progress(self, force=False):
        moment = self._clock()
        if self.stage_callback is not None and (
            force or moment - self.last_progress >= 1
        ):
            self.stage_callback(
                f"{self.operation} ({self.files} files; {self.bytes} bytes)"
            )
            self.last_progress = moment

    def finish(self, status):
        total = time.perf_counter() - self.started
        phases = " ".join(
            f"{name}_ms={value * 1000:.3f}"
            for name, value in sorted(self.timings.items())
        )
        logger.debug(
            "Backup file work: operation=%s status=%s files=%d bytes=%d %s other_ms=%.3f total_ms=%.3f",
            self.operation,
            status,
            self.files,
            self.bytes,
            phases,
            max(0.0, total - sum(self.timings.values())) * 1000,
            total * 1000,
        )
