"""Isolated providers and nonblocking operation recording."""

import asyncio
import inspect
import time
from collections.abc import Callable, Coroutine
from typing import Any, Literal
from uuid import uuid4

from .history import DiagnosticHistoryStore
from .models import (
    DiagnosticData,
    DiagnosticIssue,
    DiagnosticOptions,
    DiagnosticRecord,
    DiagnosticSection,
    DiagnosticSnapshot,
    EventsDiagnostics,
    MetricsDiagnostics,
    PluginsDiagnostics,
    PluginValues,
    RuntimeDiagnostics,
    StorageDiagnostics,
)

Provider = Callable[[], Coroutine[Any, Any, DiagnosticData]]


class Diagnostics:
    def __init__(self, history: DiagnosticHistoryStore, options: DiagnosticOptions):
        self.instance_id = uuid4().hex
        self.started_at = time.time()
        self.history = history
        self.options = options
        self.storage = StorageDiagnostics()
        self.stage: str | None = None
        self._providers: dict[str, tuple[str, Provider]] = {}
        self._pending: dict[str, asyncio.Task] = {}
        self._pending_owners: dict[str, str] = {}
        self._lock = asyncio.Lock()
        self._last_snapshot: DiagnosticSnapshot | None = None
        self.accepting = True

    def register(
        self, name: str, provider: Provider, *, owner: str = "application"
    ) -> None:
        """Register an asynchronous bounded provider under its owner's namespace."""
        if not self.accepting or not inspect.iscoroutinefunction(provider):
            raise ValueError(
                "Diagnostic providers must be asynchronous and runtime must be active"
            )
        if owner != "application" and not name.startswith(f"{owner}:"):
            raise ValueError("Plugin diagnostic names must belong to their owner")
        for key, task in list(self._pending.items()):
            if task.done() and key not in self._providers:
                self._pending.pop(key, None)
                self._pending_owners.pop(key, None)
        pending = self._pending.get(name)
        if pending is not None and not pending.done():
            raise ValueError("Previous diagnostic provider is still draining")
        pending_names = {key for key, task in self._pending.items() if not task.done()}
        if (
            len(name) > 80
            or len(set(self._providers) | pending_names) >= self.options.max_providers
        ):
            raise ValueError("Diagnostic provider capacity exceeded")
        if (
            owner != "application"
            and len(
                {key for key, item in self._providers.items() if item[0] == owner}
                | {
                    key
                    for key in pending_names
                    if self._pending_owners.get(key) == owner
                }
            )
            >= self.options.max_providers_per_owner
        ):
            raise ValueError("Diagnostic owner capacity exceeded")
        if name in self._providers:
            raise ValueError("Diagnostic provider already registered")
        self._providers[name] = owner, provider

    def remove_owner(self, owner: str) -> None:
        for name, (registered, _) in list(self._providers.items()):
            if registered == owner:
                del self._providers[name]
                task = self._pending.get(name)
                if task is not None:
                    task.cancel()

    @property
    def has_pending_providers(self) -> bool:
        return any(not task.done() for task in self._pending.values())

    def owner_pending(self, owner: str) -> bool:
        return any(
            not task.done() and self._pending_owners.get(name) == owner
            for name, task in self._pending.items()
        )

    def record_monitor_failure(
        self, name: str, error: Exception, started: float
    ) -> None:
        self.record("processes", "process_probe", started=started, error=error)

    def record(
        self,
        subsystem: str,
        operation: str,
        *,
        started: float,
        error: BaseException | None = None,
        correlation_id: str | None = None,
    ) -> None:
        """Record fixed operation labels and exception types, never exception text."""
        self.history.enqueue(
            DiagnosticRecord(
                id=uuid4().hex,
                instance_id=self.instance_id,
                timestamp=time.time(),
                subsystem=subsystem,
                operation=operation,
                outcome=(
                    "cancelled"
                    if isinstance(error, asyncio.CancelledError)
                    else "failed" if error else "completed"
                ),
                code=f"{subsystem}_{'failed' if error else 'completed'}",
                error_type=type(error).__name__[:80] if error else None,
                correlation_id=correlation_id,
                duration_ms=max(0, (time.monotonic() - started) * 1000),
            )
        )

    def record_task(
        self, task_id, record, *, started: float, owner: str | None
    ) -> None:
        self.history.enqueue(
            DiagnosticRecord(
                id=uuid4().hex,
                instance_id=self.instance_id,
                timestamp=time.time(),
                subsystem="tasks",
                operation="background_task",
                owner=owner[:160] if owner is not None else None,
                outcome=record.status,
                code=(
                    record.error.code[:80] if record.error else f"task_{record.status}"
                ),
                operation_id=task_id,
                duration_ms=max(0, (time.monotonic() - started) * 1000),
            )
        )

    def record_event(self, record) -> None:
        """Persist only event failure metadata; payloads and cancellation text stay out."""
        for failure in record.failures[:20]:
            self.history.enqueue(
                DiagnosticRecord(
                    id=uuid4().hex,
                    instance_id=self.instance_id,
                    timestamp=record.timestamp,
                    subsystem="events",
                    operation=record.name,
                    outcome="failed",
                    code=failure.code,
                    error_type=failure.error_type[:80],
                    correlation_id=record.correlation_id,
                    duration_ms=max(0, record.duration_ms),
                    owner=failure.owner[:160],
                )
            )

    async def _collect(
        self, name: str, owner: str, provider: Provider
    ) -> DiagnosticSection:
        started = time.monotonic()
        task = self._pending.get(name)
        if task is None:
            task = asyncio.create_task(provider(), name=f"diagnostic:{name}")
            self._pending[name] = task
            self._pending_owners[name] = owner
            task.add_done_callback(
                lambda finished: (
                    finished.exception() if not finished.cancelled() else None
                )
            )
        done, _ = await asyncio.wait(
            {task}, timeout=self.options.provider_timeout_seconds
        )
        if not done:
            task.cancel()
            return DiagnosticSection(
                name=name,
                owner=owner,
                status="unavailable",
                collected_at=time.time(),
                duration_ms=max(0, (time.monotonic() - started) * 1000),
                issues=[
                    DiagnosticIssue(
                        code="provider_timeout",
                        message="Diagnostic provider exceeded its deadline.",
                    )
                ],
            )
        self._pending.pop(name, None)
        self._pending_owners.pop(name, None)
        try:
            data = task.result()
            if owner != "application" and not isinstance(data, PluginValues):
                raise ValueError("Plugin providers must return PluginValues")
            status, issues = self._health(data)
            return DiagnosticSection(
                name=name,
                owner=owner,
                status=status,
                issues=issues,
                collected_at=time.time(),
                duration_ms=(time.monotonic() - started) * 1000,
                data=data,
            )
        except (Exception, asyncio.CancelledError):
            return DiagnosticSection(
                name=name,
                owner=owner,
                status="unavailable",
                collected_at=time.time(),
                duration_ms=max(0, (time.monotonic() - started) * 1000),
                issues=[
                    DiagnosticIssue(
                        code="provider_failed",
                        message="Diagnostic provider is unavailable.",
                    )
                ],
            )

    @staticmethod
    def _health(
        data: DiagnosticData,
    ) -> tuple[Literal["ok", "degraded", "unknown"], list[DiagnosticIssue]]:
        issues = []
        status: Literal["ok", "degraded", "unknown"] = (
            "unknown" if isinstance(data, PluginValues) else "ok"
        )
        if isinstance(data, StorageDiagnostics) and data.last_error_type is not None:
            issues.append(
                DiagnosticIssue(
                    code="storage_write_failed",
                    severity="error",
                    message="The last observed write failed.",
                )
            )
        elif isinstance(data, StorageDiagnostics) and not data.attempts:
            status = "unknown"
        elif isinstance(data, RuntimeDiagnostics) and data.phase == "failed":
            issues.append(
                DiagnosticIssue(
                    code="runtime_failed",
                    severity="error",
                    message="Application lifecycle failed.",
                )
            )
        elif isinstance(data, EventsDiagnostics) and data.activity.pending_workers >= (
            data.capacity.max_workers or data.capacity.max_active
        ):
            issues.append(
                DiagnosticIssue(
                    code="event_capacity_reached",
                    message="Event workers have reached capacity.",
                )
            )
        elif isinstance(data, MetricsDiagnostics):
            if data.last_sample_at is None:
                status = "unknown"
            elif (
                data.sample_age_seconds is not None
                and data.interval_seconds is not None
                and data.sample_age_seconds > data.interval_seconds * 3
            ):
                issues.append(
                    DiagnosticIssue(
                        code="metrics_stale",
                        message="The metrics sampler has missed expected updates.",
                    )
                )
        elif isinstance(data, PluginsDiagnostics) and any(
            plugin.status == "ERROR" for plugin in data.plugins
        ):
            issues.append(
                DiagnosticIssue(
                    code="plugin_failed", message="One or more plugins failed to load."
                )
            )
        return ("degraded" if issues else status), issues

    async def snapshot(self, subsystem: str | None = None) -> DiagnosticSnapshot:
        if self._lock.locked() and self._last_snapshot is not None:
            cached = self._last_snapshot.model_copy(deep=True)
            if subsystem is not None:
                cached.sections = [
                    section for section in cached.sections if section.name == subsystem
                ]
            return cached
        try:
            await asyncio.wait_for(
                self._lock.acquire(), timeout=self.options.provider_timeout_seconds * 2
            )
        except TimeoutError as error:
            from ..error import DependencyUnavailableError

            raise DependencyUnavailableError(
                "Diagnostics collection is busy"
            ) from error
        try:
            providers = [
                (name, owner, provider)
                for name, (owner, provider) in self._providers.items()
                if subsystem is None or name == subsystem
            ]
            sections = await asyncio.gather(
                *(self._collect(*item) for item in providers)
            )
            snapshot = DiagnosticSnapshot(
                instance_id=self.instance_id,
                collected_at=time.time(),
                sections=sections,
                persistence=self.history.snapshot(),
            )
            if subsystem is None:
                self._last_snapshot = snapshot.model_copy(deep=True)
            return snapshot
        finally:
            self._lock.release()

    async def close(self) -> None:
        if not self.accepting:
            return
        self.accepting = False
        for task in self._pending.values():
            task.cancel()
        tasks = set(self._pending.values())
        if tasks:
            done, _ = await asyncio.wait(tasks, timeout=1)
            for task in done:
                if not task.cancelled():
                    task.exception()
        await self.history.close()
