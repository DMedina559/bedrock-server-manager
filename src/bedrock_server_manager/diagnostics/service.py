"""Isolated providers and nonblocking operation recording."""

import asyncio
import inspect
import platform
import time
from collections import Counter
from collections.abc import Callable, Coroutine
from importlib.metadata import PackageNotFoundError, version
from typing import Any
from uuid import uuid4

from ..events.models import EventActivityQuery, EventDiagnostics
from .history import DiagnosticHistoryStore
from .models import (
    DiagnosticData,
    DiagnosticEnvironment,
    DiagnosticFinding,
    DiagnosticIssue,
    DiagnosticOptions,
    DiagnosticRecord,
    DiagnosticReport,
    DiagnosticSection,
    DiagnosticSnapshot,
    DiagnosticSummary,
    DiagnosticTrace,
    MetricsDiagnostics,
    PluginValues,
    ProcessesDiagnostics,
    RegistryDiagnostics,
    RuntimeDiagnostics,
    StorageDiagnostics,
    TasksDiagnostics,
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
        self.stage_started_at: float | None = None
        self.stage_started_monotonic: float | None = None
        self.stage_timeout_seconds: float | None = None
        from .. import __version__

        self.environment = DiagnosticEnvironment(
            backend_version=__version__,
            python_version=platform.python_version(),
            operating_system=platform.system(),
        )
        try:
            self.environment.frontend_version = version("bsm-frontend")
        except PackageNotFoundError:
            pass
        self.event_activity_provider: Callable[
            [EventActivityQuery], EventDiagnostics | None
        ] = lambda query: None
        self.task_snapshot_provider: Callable[[], TasksDiagnostics | None] = (
            lambda: None
        )
        self.phase_provider: Callable[[], str | None] = lambda: None
        self.provider_failures = 0
        self.provider_timeouts = 0
        self.provider_rejections = 0
        self._last_success: dict[str, DiagnosticSection] = {}
        self._providers: dict[str, tuple[str, Provider]] = {}
        self._pending: dict[str, asyncio.Task] = {}
        self._pending_owners: dict[str, str] = {}
        self._lock = asyncio.Lock()
        self._last_snapshot: DiagnosticSnapshot | None = None
        self.accepting = True

    def register(
        self, name: str, provider: Provider, *, owner: str = "application"
    ) -> None:
        try:
            self._register(name, provider, owner=owner)
        except ValueError:
            self.provider_rejections += 1
            raise

    def _register(
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
        self._last_snapshot = None

    def remove_owner(self, owner: str) -> None:
        for name, (registered, _) in list(self._providers.items()):
            if registered == owner:
                del self._providers[name]
                self._last_success.pop(name, None)
                self._last_snapshot = None
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

    def _enqueue(self, **values: Any) -> None:
        try:
            self.history.enqueue(
                DiagnosticRecord(
                    backend_version=self.environment.backend_version,
                    phase=self.phase_provider(),
                    **values,
                )
            )
        except Exception:
            self.history.dropped += 1

    def registry_snapshot(self) -> RegistryDiagnostics:
        owners = Counter(
            self._pending_owners[name]
            for name, task in self._pending.items()
            if not task.done()
        )
        return RegistryDiagnostics(
            registered=len(self._providers),
            pending=sum(owners.values()),
            pending_by_owner=dict(owners),
            registered_by_owner=dict(
                Counter(owner for owner, _ in self._providers.values())
            ),
            max_providers=self.options.max_providers,
            max_providers_per_owner=self.options.max_providers_per_owner,
            failures=self.provider_failures,
            timeouts=self.provider_timeouts,
            rejected=self.provider_rejections,
        )

    def summary(self, sections: list[DiagnosticSection]) -> DiagnosticSummary:
        counts = dict(Counter(section.status for section in sections))
        findings = [
            DiagnosticFinding(subsystem=section.name, owner=section.owner, issue=issue)
            for section in sections
            for issue in section.issues
        ]
        runtime = next(
            (
                section
                for section in sections
                if isinstance(section.data, RuntimeDiagnostics)
            ),
            None,
        )
        ready = bool(
            runtime is not None
            and runtime.status == "ok"
            and not runtime.stale
            and isinstance(runtime.data, RuntimeDiagnostics)
            and runtime.data.ready
        )
        status = (
            "degraded"
            if findings
            and (
                ready or any(finding.issue.severity == "error" for finding in findings)
            )
            else (
                "unknown"
                if not ready or counts.get("unknown")
                else "unavailable" if counts.get("unavailable") else "ok"
            )
        )
        return DiagnosticSummary(
            status=status,
            ready=ready,
            counts_by_status=counts,
            findings=findings[:100],
            truncated=len(findings) > 100,
        )

    def _unavailable(
        self, name: str, owner: str, started: float, code: str
    ) -> DiagnosticSection:
        previous = self._last_success.get(name)
        observed_at = previous.observed_at if previous else None
        return DiagnosticSection(
            name=name,
            owner=owner,
            status="unavailable",
            collected_at=time.time(),
            observed_at=observed_at,
            last_success_at=previous.last_success_at if previous else None,
            age_seconds=(
                max(0, time.time() - observed_at) if observed_at is not None else None
            ),
            stale=previous is not None,
            data=(
                previous.data.model_copy(deep=True)
                if previous and previous.data
                else None
            ),
            duration_ms=max(0, (time.monotonic() - started) * 1000),
            issues=[
                DiagnosticIssue(
                    code=code,
                    message="Diagnostic provider is unavailable.",
                    action="inspect_logs",
                )
            ],
        )

    def record_transport_failure(
        self, reason: str, error: BaseException | None
    ) -> None:
        self._enqueue(
            id=uuid4().hex,
            instance_id=self.instance_id,
            timestamp=time.time(),
            subsystem="transport",
            operation="send",
            outcome="failed",
            code=f"transport_{reason}",
            error_type=type(error).__name__[:80] if error else None,
            duration_ms=None,
        )

    def record_plugin_failure(
        self, owner: str, operation: str, error: BaseException | None
    ) -> None:
        self._enqueue(
            id=uuid4().hex,
            instance_id=self.instance_id,
            timestamp=time.time(),
            subsystem="plugins",
            operation=operation,
            owner=owner[:160],
            outcome=(
                "cancelled" if isinstance(error, asyncio.CancelledError) else "failed"
            ),
            code=f"plugin_{operation}_failed",
            error_type=type(error).__name__[:80] if error else None,
            duration_ms=None,
        )

    def record_monitor_failure(
        self, name: str, error: Exception, started: float
    ) -> None:
        self.record(
            "processes", "process_probe", started=started, error=error, owner=name
        )

    def record(
        self,
        subsystem: str,
        operation: str,
        *,
        started: float,
        error: BaseException | None = None,
        correlation_id: str | None = None,
        owner: str | None = None,
        operation_id: str | None = None,
    ) -> None:
        """Record fixed labels and exception types without making recording mandatory."""
        self._enqueue(
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
            code=f"{subsystem}_{'cancelled' if isinstance(error, asyncio.CancelledError) else 'failed' if error else 'completed'}",
            error_type=type(error).__name__[:80] if error else None,
            correlation_id=correlation_id,
            owner=owner[:160] if owner else None,
            operation_id=operation_id,
            duration_ms=max(0, (time.monotonic() - started) * 1000),
        )

    def record_task(
        self,
        task_id,
        record,
        *,
        started: float,
        owner: str | None,
        name: str = "background_task",
        correlation_id: str | None = None,
    ) -> None:
        self._enqueue(
            id=uuid4().hex,
            instance_id=self.instance_id,
            timestamp=time.time(),
            subsystem="tasks",
            operation=name[:160],
            owner=owner[:160] if owner else None,
            outcome=record.status,
            code=record.error.code[:80] if record.error else f"task_{record.status}",
            operation_id=task_id,
            correlation_id=correlation_id,
            duration_ms=max(0, (time.monotonic() - started) * 1000),
        )

    def record_event(self, record) -> None:
        """Persist listener failure identities and correlation without payloads."""
        for failure in record.failures[:20]:
            self._enqueue(
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
                operation_id=record.event_id,
            )

    async def _collect(
        self, name: str, owner: str, provider: Provider
    ) -> DiagnosticSection:
        started = time.monotonic()
        task = self._pending.get(name)
        if task is not None and task.done():
            self._pending.pop(name, None)
            self._pending_owners.pop(name, None)
            task = None
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
            self.provider_timeouts += 1
            self.record(
                "diagnostics", name, started=started, error=TimeoutError(), owner=owner
            )
            return self._unavailable(name, owner, started, "provider_timeout")
        self._pending.pop(name, None)
        self._pending_owners.pop(name, None)
        try:
            data = task.result()
            if owner != "application" and not isinstance(data, PluginValues):
                raise ValueError("Plugin providers must return PluginValues")
            status, issues = self._health(data)
            observed_at = (
                data.last_sample_at
                if isinstance(data, MetricsDiagnostics)
                else (
                    data.last_monitor_at
                    if isinstance(data, ProcessesDiagnostics)
                    else time.time()
                )
            )
            age = max(0, time.time() - observed_at) if observed_at is not None else None
            section = DiagnosticSection(
                name=name,
                owner=owner,
                status=status,
                issues=issues,
                collected_at=time.time(),
                duration_ms=(time.monotonic() - started) * 1000,
                data=data,
                observed_at=observed_at,
                last_success_at=time.time(),
                age_seconds=age,
                stale=age is not None and age > self.options.stale_after_seconds,
            )
            self._last_success[name] = section.model_copy(deep=True)
            return section
        except (Exception, asyncio.CancelledError) as error:
            self.provider_failures += 1
            self.record("diagnostics", name, started=started, error=error, owner=owner)
            return self._unavailable(name, owner, started, "provider_failed")

    def _health(self, data: DiagnosticData):
        from .health import evaluate_health

        return evaluate_health(data, self.options)

    async def snapshot(self, subsystem: str | None = None) -> DiagnosticSnapshot:
        if not self.accepting:
            from ..error import DependencyUnavailableError

            raise DependencyUnavailableError("Diagnostics collection is closed")
        if self._lock.locked() and self._last_snapshot is not None:
            cached = self._last_snapshot.model_copy(deep=True)
            for section in cached.sections:
                section.age_seconds = max(
                    0, time.time() - (section.observed_at or section.collected_at)
                )
                section.stale = (
                    section.stale
                    or section.age_seconds > self.options.stale_after_seconds
                )
            cached.persistence = self.history.snapshot()
            cached.registry = self.registry_snapshot()
            if subsystem is not None:
                cached.sections = [
                    section for section in cached.sections if section.name == subsystem
                ]
            cached.summary = self.summary(cached.sections)
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
                summary=self.summary(sections),
                registry=self.registry_snapshot(),
                environment=self.environment.model_copy(deep=True),
                persistence=self.history.snapshot(),
            )
            if subsystem is None:
                self._last_snapshot = snapshot.model_copy(deep=True)
            return snapshot
        finally:
            self._lock.release()

    async def trace(
        self, correlation_id: str, *, limit: int = 100, cursor: str | None = None
    ) -> DiagnosticTrace:
        """Read correlated live and retained metadata without operation inputs."""
        from ..error import UserInputError

        if not correlation_id or len(correlation_id) > 160:
            raise UserInputError(
                "Correlation identity must contain 1 to 160 characters"
            )
        history = await self.history.read(
            limit=limit, cursor=cursor, correlation_id=correlation_id
        )
        events = self.event_activity_provider(
            EventActivityQuery(correlation_id=correlation_id, limit=min(limit, 100))
        )
        truncated = False
        if events is not None:
            for record in events.active + events.recent:
                record.cancellation_reason = None
                truncated = truncated or len(record.listeners) > 50
                record.listeners = record.listeners[:50]
        tasks = self.task_snapshot_provider()
        return DiagnosticTrace(
            correlation_id=correlation_id,
            events=events,
            tasks=(
                [task for task in tasks.tasks if task.correlation_id == correlation_id]
                if tasks
                else []
            ),
            tasks_available=tasks is not None,
            history=history,
            truncated=truncated or history.truncated,
        )

    async def report(self) -> DiagnosticReport:
        """Collect independent bounded reads; one unavailable section preserves the rest."""

        snapshot, history, runs = await asyncio.gather(
            self.snapshot(),
            self.history.read(),
            self.history.runs(current_instance=self.instance_id, limit=10),
        )
        return DiagnosticReport(snapshot=snapshot, history=history, runs=runs)

    async def close(self) -> None:
        if not self.accepting:
            return
        self.record("runtime", "diagnostics_closed", started=time.monotonic())
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
