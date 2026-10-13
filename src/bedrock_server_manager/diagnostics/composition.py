"""Wire application-owned providers at the composition boundary."""

import os
import platform
import time
from typing import TYPE_CHECKING

from .. import __version__
from ..state_revision import revision_clock
from .history import DiagnosticHistoryStore
from .models import (
    DiagnosticOptions,
    EventsDiagnostics,
    MetricsDiagnostics,
    ProcessDiagnostic,
    ProcessesDiagnostics,
    RuntimeDiagnostics,
    StateDiagnostics,
)
from .service import Diagnostics

if TYPE_CHECKING:
    from ..context import AppContext


def configure_diagnostics(context: "AppContext") -> Diagnostics:
    """Compose metadata providers without eagerly initializing runtime services."""
    options = DiagnosticOptions.model_validate(context.settings.get("diagnostics", {}))
    service = Diagnostics(DiagnosticHistoryStore(context.db, options), options)
    service.event_activity_provider = lambda query: (
        context._events.diagnostics(query) if context._events else None
    )
    service.task_snapshot_provider = lambda: (
        context._task_manager.diagnostic_snapshot() if context._task_manager else None
    )
    service.phase_provider = lambda: context.lifecycle_phase
    service.environment.database_dialect = (
        context.db.engine.dialect.name if context.db.engine else None
    )
    service.environment.database_schema_revision = context.db.schema_revision

    async def runtime():
        web = (
            context._web_runtime.snapshot()
            if context._web_runtime is not None
            else None
        )
        return RuntimeDiagnostics(
            ready=context.lifecycle_phase == "ready"
            and (web is None or web.phase == "ready"),
            stage_started_at=service.stage_started_at,
            stage_elapsed_seconds=(
                max(0, time.monotonic() - service.stage_started_monotonic)
                if service.stage_started_monotonic is not None
                else None
            ),
            stage_timeout_seconds=service.stage_timeout_seconds,
            phase=context.lifecycle_phase,
            stage=service.stage,
            shutdown_requested=web.shutdown_requested if web else None,
            shutdown_reason=web.shutdown_reason if web else None,
            pid=os.getpid(),
            uptime_seconds=max(0, time.time() - service.started_at),
            version=__version__,
            python_version=platform.python_version(),
        )

    async def state():
        current = context.state
        async with current.lock:
            stamp = revision_clock.capture()
            ages = [
                group.dirty_age_seconds
                for group in (
                    current.settings,
                    current.servers,
                    current.plugins,
                    current.users,
                )
            ]
            pending_ages = [age for age in ages if age is not None]
            return StateDiagnostics(
                epoch=stamp["epoch"],
                observation_revision=stamp["revision"],
                counts={
                    "servers": current.servers.count,
                    "plugins": current.plugins.count,
                    "users": current.users.count,
                },
                oldest_pending_age_seconds=max(pending_ages) if pending_ages else None,
                pending_changes={
                    "servers": len(current.servers.dirty_servers),
                    "plugins": len(current.plugins.dirty_plugins),
                    "users": len(current.users.dirty_users),
                    "settings": int(current.settings.is_dirty),
                },
            )

    async def storage():
        return context.storage.diagnostic_snapshot()

    async def events():
        from ..events.models import EventActivityQuery

        bus = context._events
        if bus is None:
            raise RuntimeError("Event subsystem not initialized")
        activity = bus.diagnostics(EventActivityQuery(limit=options.event_record_limit))
        for record in activity.active + activity.recent:
            record.cancellation_reason = None
        return EventsDiagnostics(
            activity=activity, capacity=bus.options.model_copy(deep=True)
        )

    async def transport():
        manager = context._connection_manager
        if manager is None:
            raise RuntimeError("Transport not initialized")
        return manager.diagnostic_snapshot()

    async def plugins():
        manager = context._plugin_manager
        if manager is None:
            raise RuntimeError("Plugins not initialized")
        from ..events.models import EventActivityQuery

        activity = context.events.diagnostics(EventActivityQuery(limit=1))
        owned = (
            context._task_manager.diagnostic_snapshot().tasks
            if context._task_manager
            else []
        )
        return manager.diagnostic_snapshot(
            event_activity=activity,
            registered_providers=service.registry_snapshot().registered_by_owner,
            managed_tasks=owned,
        )

    async def tasks():
        manager = context._task_manager
        if manager is None:
            raise RuntimeError("Tasks not initialized")
        return manager.diagnostic_snapshot()

    async def processes():
        current = context.state
        observed = current.runtime.servers
        registered = current.servers.servers
        manager = context._bedrock_process_manager
        return ProcessesDiagnostics(
            processes=[
                ProcessDiagnostic(
                    server_name=name,
                    expected_status=record.status,
                    observed_running=(
                        observed[name].running if name in observed else None
                    ),
                    pid=observed[name].pid if name in observed else None,
                    observed_at=(
                        manager.monitor_observations.get(name) if manager else None
                    ),
                    last_error_type=(
                        manager.monitor_errors.get(name) if manager else None
                    ),
                )
                for name, record in list(registered.items())[:100]
            ],
            truncated=len(registered) > 100,
            last_monitor_at=manager.monitor_observed_at if manager else None,
            monitor_failures=manager.monitor_failures if manager else None,
            registered=current.servers.count,
            observed_running=sum(value.running for value in observed.values()),
            observation_available=context._bedrock_process_manager is not None,
        )

    async def metrics():
        manager = context._metrics_service
        if manager is None:
            return MetricsDiagnostics()
        return manager.diagnostic_snapshot()

    for name, provider in (
        ("runtime", runtime),
        ("state", state),
        ("storage", storage),
        ("events", events),
        ("transport", transport),
        ("plugins", plugins),
        ("tasks", tasks),
        ("processes", processes),
        ("metrics", metrics),
    ):
        service.register(name, provider)
    if context._events is not None:
        context._events.diagnostic_recorder = service.record_event
    return service
