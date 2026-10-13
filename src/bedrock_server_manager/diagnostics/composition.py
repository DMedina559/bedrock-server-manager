"""Wire application-owned providers at the composition boundary."""

import os
import platform
import time
from collections import Counter
from typing import TYPE_CHECKING

from .. import __version__
from ..state_revision import revision_clock
from .history import DiagnosticHistoryStore
from .models import (
    DiagnosticOptions,
    EventsDiagnostics,
    MetricsDiagnostics,
    PluginDiagnostic,
    PluginsDiagnostics,
    ProcessDiagnostic,
    ProcessesDiagnostics,
    RuntimeDiagnostics,
    StateDiagnostics,
    TaskDiagnostic,
    TasksDiagnostics,
    TransportDiagnostics,
)
from .service import Diagnostics

if TYPE_CHECKING:
    from ..context import AppContext


def configure_diagnostics(context: "AppContext") -> Diagnostics:
    """Compose metadata providers without eagerly initializing runtime services."""
    options = DiagnosticOptions.model_validate(context.settings.get("diagnostics", {}))
    service = Diagnostics(DiagnosticHistoryStore(context.db, options), options)

    async def runtime():
        web = (
            context._web_runtime.snapshot()
            if context._web_runtime is not None
            else None
        )
        return RuntimeDiagnostics(
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
        return service.storage.model_copy(deep=True)

    async def events():
        from ..events.models import EventActivityQuery

        bus = context._events
        if bus is None:
            raise RuntimeError("Event subsystem not initialized")
        activity = bus.diagnostics(EventActivityQuery(limit=20))
        for record in activity.active + activity.recent:
            record.cancellation_reason = None
        return EventsDiagnostics(
            activity=activity, capacity=bus.options.model_copy(deep=True)
        )

    async def transport():
        manager = context._connection_manager
        if manager is None:
            raise RuntimeError("Transport not initialized")
        return TransportDiagnostics(
            connected_clients=len(manager.active_connections),
            subscriptions=sum(
                len(clients) for clients in manager.subscriptions.values()
            ),
            topics=len(manager.subscriptions),
            successful_sends=manager.successful_sends,
            failed_sends=manager.failed_sends,
        )

    async def plugins():
        manager = context._plugin_manager
        if manager is None:
            raise RuntimeError("Plugins not initialized")
        names = sorted(context.state.plugins.plugins)
        return PluginsDiagnostics(
            total=len(names),
            truncated=len(names) > 100,
            plugins=[
                PluginDiagnostic(
                    name=name,
                    status=manager.get_plugin_status(name),
                    generation=manager.events.owner_generation(f"plugin:{name}"),
                    active_tasks=len(manager.get_plugin_runtime(name).active_tasks),
                    draining=name in manager._draining_plugins
                    or manager.diagnostic_pending(name),
                )
                for name in names[:100]
            ],
        )

    async def tasks():
        manager = context._task_manager
        if manager is None:
            raise RuntimeError("Tasks not initialized")
        return TasksDiagnostics(
            tasks=[
                TaskDiagnostic(
                    id=task_id,
                    owner=manager._plugin_owners.get(task_id),
                    status=record.status,
                    error_code=record.error.code if record.error else None,
                    elapsed_seconds=(
                        (manager._timing[task_id][1] or time.monotonic())
                        - manager._timing[task_id][0]
                        if task_id in manager._timing
                        else None
                    ),
                )
                for task_id, record in manager.tasks.items()
            ],
            active=manager.active_task_count,
            counts_by_status=dict(
                Counter(item.status for item in manager.tasks.values())
            ),
            accepting=not manager._shutdown_started,
        )

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
        if manager is None or not manager._history:
            return MetricsDiagnostics()
        sampled = manager._history[-1].timestamp
        return MetricsDiagnostics(
            last_sample_at=sampled,
            sample_age_seconds=max(0, time.time() - sampled),
            interval_seconds=manager.interval_seconds,
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
    ):
        service.register(name, provider)
    if context._events is not None:
        context._events.diagnostic_recorder = service.record_event
    return service
