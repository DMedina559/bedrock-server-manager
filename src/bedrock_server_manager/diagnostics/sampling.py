"""Optional lifecycle-owned persistence of compact health observations."""

import asyncio
import json
import time
from collections.abc import Callable, Coroutine
from typing import Any, Literal
from uuid import uuid4

from .models import CollectionDiagnostics, DiagnosticHealthSample, DiagnosticSnapshot


class HealthSampler:
    """Sample independently of domain transactions and never retain full snapshots."""

    def __init__(
        self,
        *,
        interval: float | None,
        collect: Callable[[], Coroutine[Any, Any, DiagnosticSnapshot]],
        record: Callable[..., None],
        instance_id: str,
        telemetry: CollectionDiagnostics,
    ) -> None:
        self.interval = interval
        self.collect = collect
        self.record = record
        self.instance_id = instance_id
        self.telemetry = telemetry
        self._task: asyncio.Task | None = None
        self._signature: str | None = None
        self._closed = False

    @property
    def status(
        self,
    ) -> Literal["disabled", "not_started", "running", "stopped", "failed"]:
        if self.interval is None:
            return "disabled"
        if self._closed:
            return "stopped"
        if self._task is None:
            return "not_started"
        return "failed" if self._task.done() else "running"

    def _finished(self, task: asyncio.Task) -> None:
        error = None if task.cancelled() else task.exception()
        if not self._closed:
            self.telemetry.periodic_failures += 1
            self.telemetry.last_periodic_error_type = (
                "CancelledError"
                if task.cancelled()
                else type(error).__name__ if error else "RuntimeError"
            )

    def start(self) -> None:
        if not self._closed and self.interval is not None and self._task is None:
            self._task = asyncio.create_task(self._run(), name="diagnostics-periodic")
            self._task.add_done_callback(self._finished)

    async def record_once(self) -> None:
        """Observe sample success/failure independently from journal write success."""
        try:
            await self._record_once()
        except Exception as error:
            self.telemetry.periodic_failures += 1
            self.telemetry.last_periodic_error_type = type(error).__name__
            raise
        self.telemetry.last_periodic_success_at = time.time()
        self.telemetry.last_periodic_error_type = None

    async def _record_once(self) -> None:
        started = time.monotonic()
        snapshot = await self.collect()
        health = DiagnosticHealthSample(
            status=snapshot.summary.status,
            ready=snapshot.summary.ready,
            sections={section.name: section.status for section in snapshot.sections},
        )
        signature = json.dumps(
            health.model_dump(), sort_keys=True, separators=(",", ":")
        )
        code = (
            "health_transition"
            if self._signature is not None and self._signature != signature
            else "health_sample"
        )
        self.record(
            id=uuid4().hex,
            instance_id=self.instance_id,
            timestamp=time.time(),
            subsystem="diagnostics",
            operation="periodic_health",
            outcome="completed",
            code=code,
            health=health,
            duration_ms=max(0, (time.monotonic() - started) * 1000),
        )
        self._signature = signature
        self.telemetry.periodic_cycles += 1

    async def _run(self) -> None:
        assert self.interval is not None
        while True:
            await asyncio.sleep(self.interval)
            try:
                await self.record_once()
            except Exception:
                pass

    async def close(self) -> None:
        self._closed = True
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None
