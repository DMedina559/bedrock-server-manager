"""Wire application-owned providers at the composition boundary."""

import os
import platform
import time
from typing import TYPE_CHECKING

from .. import __version__
from ..events.operations import OperationActivityQuery
from ..state.revision import revision_clock
from .history import DiagnosticHistoryStore
from .models import (
    BackupsDiagnostics,
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
    service.operation_activity_provider = lambda query: (
        context._events.operations.activity(query) if context._events else None
    )
    service.subscription_activity_provider = lambda query: (
        context._events.subscription_snapshot(
            query.limit, name=query.name, owner=query.owner
        )
        if context._events
        else None
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
        from ..utils.threads import worker_snapshot

        workers = worker_snapshot()
        return RuntimeDiagnostics(
            running_workers=workers["running"],
            queued_workers=workers["queued"],
            draining_workers=workers["draining"],
            oldest_draining_worker_seconds=workers["oldest_draining_seconds"],
            pending_lifecycle_stages=sorted(
                task.get_name() for task in context._lifecycle_tasks if not task.done()
            ),
            ready=context.is_ready,
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
                    "schedules": current.scheduler.count,
                    "servers": current.servers.count,
                    "plugins": current.plugins.count,
                    "users": current.users.count,
                },
                oldest_pending_age_seconds=max(pending_ages) if pending_ages else None,
                pending_changes={
                    "servers": len(current.servers.dirty_servers),
                    "plugins": len(current.plugins.dirty_plugins),
                    "users": len(current.users.dirty_users),
                    "schedules": 0,  # Schedules publish only committed state.
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
            activity=activity,
            capacity=bus.options.model_copy(deep=True),
            operations=bus.operations.activity(
                OperationActivityQuery(limit=options.event_record_limit)
            ),
            subscriptions=bus.subscription_snapshot(options.event_detail_limit),
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

        proc_diagnostics: list[ProcessDiagnostic] = []
        total_cpu = 0.0
        total_mem = 0.0
        unhealthy = 0
        untracked_count = 0
        command_unavailable = 0

        for name, record in registered.items():
            rt_info = observed.get(name)
            is_running = (
                rt_info.running
                if rt_info and rt_info.process_observed_at is not None
                else None
            )
            pid = rt_info.pid if rt_info else None
            cpu = rt_info.cpu_percent if rt_info and is_running else None
            mem = rt_info.memory_mb if rt_info and is_running else None
            restarts = manager.restart_attempts.get(name, 0) if manager else 0
            in_backoff = (
                time.monotonic() < manager._restart_after.get(name, 0)
                if manager
                else False
            )
            is_recovered = (
                rt_info.recovered_untracked if rt_info and is_running else False
            )
            command_available = bool(rt_info and rt_info.command_available)
            exhausted = bool(manager and name in manager.recovery_failures)
            last_error = manager.monitor_errors.get(name) if manager else None
            if is_running and not command_available:
                command_unavailable += 1
            if is_recovered:
                untracked_count += 1

            is_healthy = None if is_running is None else True
            if (
                exhausted
                or last_error
                or restarts > 0
                or in_backoff
                or (is_running and not command_available)
                or (record.status == "RUNNING" and is_running is False)
                or (record.status == "STOPPED" and is_running is True)
            ):
                is_healthy = False
            if is_healthy is False:
                unhealthy += 1

            if is_running and cpu is not None:
                total_cpu += cpu
            if is_running and mem is not None:
                total_mem += mem

            proc_diagnostics.append(
                ProcessDiagnostic(
                    server_name=name,
                    expected_status=record.status,
                    observed_running=is_running,
                    pid=pid,
                    observed_at=(rt_info.process_observed_at if rt_info else None),
                    last_error_type=last_error,
                    cpu_percent=cpu,
                    memory_mb=mem,
                    restart_attempts=restarts,
                    in_restart_backoff=in_backoff,
                    recovered_untracked=is_recovered,
                    process_owned=bool(rt_info and rt_info.process_owned),
                    command_available=command_available,
                    output_source=rt_info.output_source if rt_info else "unknown",
                    recovery_exhausted=exhausted,
                    healthy=is_healthy,
                )
            )

        return ProcessesDiagnostics(
            processes=proc_diagnostics[:100],
            truncated=len(registered) > 100,
            last_monitor_at=manager.monitor_observed_at if manager else None,
            monitor_failures=manager.monitor_failures if manager else None,
            registered=current.servers.count,
            observed_running=sum(value.running for value in observed.values()),
            observation_available=manager is not None
            or any(
                record.process_observed_at is not None for record in observed.values()
            ),
            total_cpu_percent=round(total_cpu, 2),
            total_memory_mb=round(total_mem, 2),
            unhealthy_count=unhealthy,
            untracked_recoveries_count=untracked_count,
            command_unavailable_count=command_unavailable,
        )

    async def metrics():
        manager = context._metrics_service
        if manager is None:
            return MetricsDiagnostics()
        return manager.diagnostic_snapshot()

    async def backups():
        health = []
        for name in list(context.state.servers.servers)[:100]:
            server = context.get_server(name, require_installation=False)
            if server.operation_lock.locked():
                continue
            health.append(await server.backups.backup_health())
        return BackupsDiagnostics(
            servers=len(health),
            archives=sum(h.count for h in health),
            total_bytes=sum(h.total_bytes for h in health),
            failed=sum(h.failed_count for h in health),
            missing_keys=sum(len(h.missing_key_ids) for h in health),
            destination_failures=sum(h.destination_failures for h in health),
            without_backup=sum(h.count == 0 for h in health),
        )

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
        ("backups", backups),
        ("scheduler", context.scheduler.diagnostic_snapshot),
    ):
        service.register(name, provider)
    if context._events is not None:
        context._events.diagnostic_recorder = service.record_event
    return service
