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

from ..events.models import EventActivityQuery, EventDiagnostics, EventSubscriptions
from ..operations import OperationActivity, OperationActivityQuery
from .activity import (
    RecentOutcomes,
    bound_event_activity,
    bound_operations,
    bound_subscriptions,
)
from .health import summarize_health
from .history import DiagnosticHistoryStore
from .models import (
    CollectionDiagnostics,
    DiagnosticActivity,
    DiagnosticData,
    DiagnosticEnvironment,
    DiagnosticIssue,
    DiagnosticOptions,
    DiagnosticRecord,
    DiagnosticReport,
    DiagnosticSection,
    DiagnosticSnapshot,
    DiagnosticSummary,
    DiagnosticTrace,
    EventsDiagnostics,
    MetricsDiagnostics,
    PluginValues,
    ProcessesDiagnostics,
    RegistryDiagnostics,
    TasksDiagnostics,
)
from .sampling import HealthSampler

Provider = Callable[[], Coroutine[Any, Any, DiagnosticData]]


class Diagnostics:
    def __init__(self, history: DiagnosticHistoryStore, options: DiagnosticOptions):
        self.instance_id = uuid4().hex
        self.started_at = time.time()
        self.history = history
        self.options = options
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
        self.operation_activity_provider: Callable[
            [OperationActivityQuery], OperationActivity | None
        ] = lambda query: None
        self.subscription_activity_provider: Callable[
            [EventActivityQuery], EventSubscriptions | None
        ] = lambda query: None
        self.task_snapshot_provider: Callable[[], TasksDiagnostics | None] = (
            lambda: None
        )
        self.phase_provider: Callable[[], str | None] = lambda: None
        self.collection = CollectionDiagnostics()
        self.recent = RecentOutcomes()
        self._timed_out: set[asyncio.Task] = set()
        self._sampler = HealthSampler(
            interval=options.snapshot_interval_seconds,
            collect=self.snapshot,
            record=self._enqueue,
            instance_id=self.instance_id,
            telemetry=self.collection,
        )
        self.provider_failures = 0
        self.provider_timeouts = 0
        self.provider_rejections = 0
        self._last_success: dict[str, DiagnosticSection] = {}
        self._providers: dict[str, tuple[str, Provider]] = {}
        self._registrations: dict[str, object] = {}
        self._registration_revision = 0
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
        self._registrations[name] = object()
        self._registration_revision += 1
        self._last_snapshot = None

    def remove_owner(self, owner: str) -> None:
        for name, (registered, _) in list(self._providers.items()):
            if registered == owner:
                del self._providers[name]
                self._registrations.pop(name, None)
                self._registration_revision += 1
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
            record = DiagnosticRecord(
                backend_version=self.environment.backend_version,
                phase=self.phase_provider(),
                **values,
            )
            self.recent.record(record.subsystem, record.outcome, record.code)
            self.history.enqueue(record)
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
        return summarize_health(sections, self.collection_snapshot())

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
        code: str | None = None,
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
            code=code
            or f"{subsystem}_{'cancelled' if isinstance(error, asyncio.CancelledError) else 'failed' if error else 'completed'}",
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
        self, name: str, owner: str, provider: Provider, registration: object
    ) -> DiagnosticSection | None:
        if self._registrations.get(name) is not registration:
            return None
        started = time.monotonic()
        task = self._pending.get(name)
        if task is not None and task.done():
            self._timed_out.discard(task)
            self._pending.pop(name, None)
            self._pending_owners.pop(name, None)
            task = None
        if task is not None and task in self._timed_out:
            return self._unavailable(name, owner, started, "provider_draining")
        if task is None:
            task = asyncio.create_task(provider(), name=f"diagnostic:{name}")
            self._pending[name] = task
            self._pending_owners[name] = owner
            task.add_done_callback(self._timed_out.discard)
            task.add_done_callback(
                lambda finished: (
                    finished.exception() if not finished.cancelled() else None
                )
            )
        done, _ = await asyncio.wait(
            {task}, timeout=self.options.provider_timeout_seconds
        )
        if self._registrations.get(name) is not registration:
            if task.done() and self._pending.get(name) is task:
                self._pending.pop(name, None)
                self._pending_owners.pop(name, None)
            return None
        if not done:
            self._timed_out.add(task)
            task.cancel()
            self.provider_timeouts += 1
            self.record(
                "diagnostics",
                name,
                started=started,
                error=TimeoutError(),
                owner=owner,
                code="provider_timeout",
            )
            return self._unavailable(name, owner, started, "provider_timeout")
        self._pending.pop(name, None)
        self._pending_owners.pop(name, None)
        try:
            data = task.result()
            if owner != "application" and not isinstance(data, PluginValues):
                raise ValueError("Plugin providers must return PluginValues")
            if isinstance(data, EventsDiagnostics):
                data = data.model_copy(deep=True)
                data.activity, truncated = bound_event_activity(
                    data.activity,
                    records=self.options.event_record_limit,
                    details=self.options.event_detail_limit,
                )
                if data.operations is not None:
                    data.operations = bound_operations(
                        data.operations, records=self.options.event_record_limit
                    )
                data.subscriptions = bound_subscriptions(
                    data.subscriptions,
                    records=self.options.event_detail_limit,
                    details=self.options.event_detail_limit,
                )
                data.truncated = (
                    data.truncated
                    or truncated
                    or data.subscriptions.truncated
                    or bool(
                        data.operations
                        and (
                            data.operations.active_truncated
                            or data.operations.recent_truncated
                        )
                    )
                )
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

    def collection_snapshot(self) -> CollectionDiagnostics:
        """Expose collection and writer observations without additional I/O."""
        result = self.collection.model_copy(deep=True)
        persistence = self.history.snapshot()
        result.active = self._lock.locked()
        result.periodic_enabled = self.options.snapshot_interval_seconds is not None
        result.periodic_status = self._sampler.status
        if persistence.writer_status == "failed":
            result.status = "unavailable"
        elif (
            result.last_error_type
            or persistence.last_error_type
            or persistence.last_read_error_type
            or result.last_periodic_error_type
            or result.periodic_status == "failed"
        ):
            result.status = "degraded"
        return result

    async def snapshot(self, subsystem: str | None = None) -> DiagnosticSnapshot:
        """Collect independent observations and account for collection overhead."""
        self.collection.requests += 1
        started = time.monotonic()
        cached = self._lock.locked() and self._last_snapshot is not None
        try:
            result = await self._snapshot(subsystem)
            if not cached:
                self.collection.last_success_at = time.time()
                self.collection.last_error_type = None
                self.collection.last_duration_ms = max(
                    0, (time.monotonic() - started) * 1000
                )
            result.collection = self.collection_snapshot()
            result.recent = self.recent.snapshot()
            result.summary = summarize_health(result.sections, result.collection)
            return result
        except Exception as error:
            self.collection.failures += 1
            self.collection.last_error_type = type(error).__name__
            self.collection.last_duration_ms = max(
                0, (time.monotonic() - started) * 1000
            )
            raise

    async def _snapshot(self, subsystem: str | None = None) -> DiagnosticSnapshot:
        if not self.accepting:
            from ..error import DependencyUnavailableError

            raise DependencyUnavailableError("Diagnostics collection is closed")
        if self._lock.locked() and self._last_snapshot is not None:
            self.collection.cache_hits += 1
            self.collection.cache_age_seconds = max(
                0, time.time() - self._last_snapshot.collected_at
            )
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
            self.collection.collections += 1
            self.collection.cache_age_seconds = None
            revision = self._registration_revision
            providers = [
                (name, owner, provider, self._registrations[name])
                for name, (owner, provider) in self._providers.items()
                if subsystem is None or name == subsystem
            ]
            collected = await asyncio.gather(
                *(self._collect(*item) for item in providers)
            )
            sections = [
                section
                for section, entry in zip(collected, providers)
                if section is not None and self._registrations.get(entry[0]) is entry[3]
            ]
            snapshot = DiagnosticSnapshot(
                instance_id=self.instance_id,
                collected_at=time.time(),
                sections=sections,
                summary=self.summary(sections),
                registry=self.registry_snapshot(),
                environment=self.environment.model_copy(deep=True),
                persistence=self.history.snapshot(),
            )
            if subsystem is None and revision == self._registration_revision:
                self._last_snapshot = snapshot.model_copy(deep=True)
            return snapshot
        finally:
            self._lock.release()

    def activity(self, query: EventActivityQuery | None = None) -> DiagnosticActivity:
        """Read bounded global events, operation ancestry metadata, and listener details."""
        query = query or EventActivityQuery()
        query = query.model_copy(
            update={"limit": min(query.limit, self.options.event_record_limit)}
        )
        issues = []
        events = None
        truncated = False
        try:
            events = self.event_activity_provider(query)
            if events is not None:
                events, truncated = bound_event_activity(
                    events, records=query.limit, details=self.options.event_detail_limit
                )
        except Exception:
            events = None
            issues.append(
                DiagnosticIssue(
                    code="activity_events_unavailable",
                    message="Event observations are unavailable.",
                    action="inspect_events",
                )
            )
        operations = None
        try:
            operations = self.operation_activity_provider(
                OperationActivityQuery(
                    name=query.operation_name,
                    owner=query.owner,
                    source=query.source,
                    server_name=query.server_name,
                    operation_id=query.operation_id,
                    sequence_id=query.sequence_id,
                    correlation_id=query.correlation_id,
                    limit=query.limit,
                )
            )
            if operations is not None:
                operations = bound_operations(operations, records=query.limit)
        except Exception:
            operations = None
            issues.append(
                DiagnosticIssue(
                    code="activity_operations_unavailable",
                    message="Operation observations are unavailable.",
                    action="inspect_events",
                )
            )
        subscriptions = None
        try:
            subscriptions = self.subscription_activity_provider(
                query.model_copy(update={"limit": self.options.event_detail_limit})
            )
            if subscriptions is not None:
                subscriptions = bound_subscriptions(
                    subscriptions,
                    records=self.options.event_detail_limit,
                    details=self.options.event_detail_limit,
                )
        except Exception:
            subscriptions = None
            issues.append(
                DiagnosticIssue(
                    code="activity_subscriptions_unavailable",
                    message="Listener observations are unavailable.",
                    action="inspect_events",
                )
            )
        return DiagnosticActivity(
            events=events,
            operations=operations,
            subscriptions=subscriptions,
            issues=issues,
            truncated=truncated
            or bool(
                operations
                and (operations.active_truncated or operations.recent_truncated)
            )
            or bool(subscriptions and subscriptions.truncated),
        )

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
        issues = []
        events = None
        tasks = None
        truncated = history.truncated
        try:
            activity = self.event_activity_provider(
                EventActivityQuery(correlation_id=correlation_id, limit=min(limit, 100))
            )
            if activity is not None:
                events, detail_truncated = bound_event_activity(
                    activity,
                    records=min(limit, self.options.event_record_limit),
                    details=self.options.event_detail_limit,
                )
                truncated = truncated or detail_truncated
        except Exception:
            issues.append(
                DiagnosticIssue(
                    code="trace_events_unavailable",
                    message="Live event observations are unavailable.",
                    action="inspect_events",
                )
            )
        try:
            tasks = self.task_snapshot_provider()
        except Exception:
            issues.append(
                DiagnosticIssue(
                    code="trace_tasks_unavailable",
                    message="Live task observations are unavailable.",
                    action="inspect_logs",
                )
            )
        if not history.available:
            issues.append(
                DiagnosticIssue(
                    code="trace_history_unavailable",
                    message="Retained history is unavailable.",
                    action="inspect_storage",
                )
            )
        operations = None
        try:
            operations = self.operation_activity_provider(
                OperationActivityQuery(
                    correlation_id=correlation_id,
                    limit=min(limit, self.options.event_record_limit),
                )
            )
            if operations is not None:
                operations = bound_operations(
                    operations, records=min(limit, self.options.event_record_limit)
                )
                truncated = (
                    truncated
                    or operations.active_truncated
                    or operations.recent_truncated
                )
        except Exception:
            operations = None
            issues.append(
                DiagnosticIssue(
                    code="trace_operations_unavailable",
                    message="Operation observations are unavailable.",
                    action="inspect_events",
                )
            )
        matching_tasks = (
            [task for task in tasks.tasks if task.correlation_id == correlation_id]
            if tasks is not None
            else []
        )
        return DiagnosticTrace(
            operations=operations,
            operations_available=operations is not None,
            correlation_id=correlation_id,
            events=events,
            events_available=events is not None,
            tasks=matching_tasks[:limit],
            tasks_available=tasks is not None,
            history=history,
            issues=issues,
            truncated=truncated or len(matching_tasks) > limit,
        )

    async def report(self) -> DiagnosticReport:
        """Collect independent bounded reads; one unavailable section preserves the rest."""

        snapshot, history, runs = await asyncio.gather(
            self.snapshot(),
            self.history.read(),
            self.history.runs(current_instance=self.instance_id, limit=10),
        )
        snapshot.persistence = self.history.snapshot()
        snapshot.collection = self.collection_snapshot()
        if snapshot.collection.status == "ok" and (
            not history.available or not runs.available
        ):
            snapshot.collection.status = "degraded"
        snapshot.summary = summarize_health(snapshot.sections, snapshot.collection)
        return DiagnosticReport(snapshot=snapshot, history=history, runs=runs)

    def start(self) -> None:
        """Start recording and optional periodic observations on the owning loop."""
        if not self.accepting:
            return
        self.history.start()
        self._sampler.start()

    async def close(self) -> None:
        if not self.accepting:
            return
        await self._sampler.close()
        self.record("runtime", "diagnostics_closed", started=time.monotonic())
        self.accepting = False
        for task in self._pending.values():
            task.cancel()
        tasks = set(self._pending.values())
        if tasks:
            done, _ = await asyncio.wait(tasks, timeout=1)
            for task in done:
                self._timed_out.discard(task)
                if not task.cancelled():
                    task.exception()
        await self.history.close()
