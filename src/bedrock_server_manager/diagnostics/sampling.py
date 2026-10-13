"""Optional lifecycle-owned persistence of compact health observations."""

import asyncio
import json
import time
from collections.abc import Callable, Coroutine
from typing import Any
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

    def start(self) -> None:
        if self.interval is not None and self._task is None:
            self._task = asyncio.create_task(self._run(), name="diagnostics-periodic")

    async def record_once(self) -> None:
        """Persist one bounded health sample or transition without payloads."""
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
                self.telemetry.periodic_failures += 1

    async def close(self) -> None:
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None
