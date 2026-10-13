"""Evidence-based health rules; normal activity is separate from failure."""

from typing import Literal

from .models import (
    DiagnosticData,
    DiagnosticIssue,
    DiagnosticOptions,
    EventsDiagnostics,
    MetricsDiagnostics,
    PluginsDiagnostics,
    PluginValues,
    ProcessesDiagnostics,
    RuntimeDiagnostics,
    StateDiagnostics,
    StorageDiagnostics,
    TransportDiagnostics,
)

Status = Literal["ok", "degraded", "unknown"]


def evaluate_health(
    data: DiagnosticData, options: DiagnosticOptions
) -> tuple[Status, list[DiagnosticIssue]]:
    """Explain current evidence without inferring health from lifetime failure totals."""
    if isinstance(data, PluginValues):
        issues = (
            [
                DiagnosticIssue(
                    code="plugin_reported_degraded",
                    message="The plugin reports degraded health.",
                    action="inspect_plugins",
                )
            ]
            if data.health == "degraded"
            else []
        )
        return data.health, issues
    rules = {
        "runtime": _runtime,
        "storage": _storage,
        "events": _events,
        "metrics": _metrics,
        "plugins": _plugins,
        "processes": _processes,
        "transport": _transport,
        "state": _state,
    }
    rule = rules.get(data.kind)
    return rule(data, options) if rule is not None else ("ok", [])


def _issue(
    code: str, message: str, action, *, severity="warning"
) -> tuple[Status, list[DiagnosticIssue]]:
    return "degraded", [
        DiagnosticIssue(code=code, message=message, action=action, severity=severity)
    ]


def _runtime(
    data: DiagnosticData, options: DiagnosticOptions
) -> tuple[Status, list[DiagnosticIssue]]:
    assert isinstance(data, RuntimeDiagnostics)
    if data.phase == "failed":
        return _issue(
            "runtime_failed",
            "Application lifecycle failed.",
            "inspect_logs",
            severity="error",
        )
    return ("ok" if data.ready else "unknown"), []


def _storage(
    data: DiagnosticData, options: DiagnosticOptions
) -> tuple[Status, list[DiagnosticIssue]]:
    assert isinstance(data, StorageDiagnostics)
    if data.last_error_type or data.last_reload_error_type:
        return _issue(
            "storage_operation_failed",
            "The last observed storage operation failed.",
            "inspect_storage",
            severity="error",
        )
    return ("ok" if data.attempts or data.reload_attempts else "unknown"), []


def _events(
    data: DiagnosticData, options: DiagnosticOptions
) -> tuple[Status, list[DiagnosticIssue]]:
    assert isinstance(data, EventsDiagnostics)
    if data.activity.pending_workers >= (
        data.capacity.max_workers or data.capacity.max_active
    ):
        return _issue(
            "event_capacity_reached",
            "Event workers have reached capacity.",
            "inspect_events",
        )
    return "ok", []


def _metrics(
    data: DiagnosticData, options: DiagnosticOptions
) -> tuple[Status, list[DiagnosticIssue]]:
    assert isinstance(data, MetricsDiagnostics)
    if data.last_error_type:
        return _issue(
            "metrics_collection_failed",
            "The last metrics collection failed.",
            "inspect_logs",
        )
    if data.last_sample_at is None or data.warming_up:
        return "unknown", []
    if data.sample_age_seconds is None or data.interval_seconds is None:
        return "unknown", []
    if data.sample_age_seconds > max(
        options.stale_after_seconds, data.interval_seconds * 3
    ):
        return _issue(
            "metrics_stale",
            "The metrics sampler has missed expected updates.",
            "inspect_logs",
        )
    if data.unavailable_measurements:
        return _issue(
            "metrics_readings_unavailable",
            "Some resource measurements are unavailable.",
            "inspect_logs",
        )
    return "ok", []


def _plugins(
    data: DiagnosticData, options: DiagnosticOptions
) -> tuple[Status, list[DiagnosticIssue]]:
    assert isinstance(data, PluginsDiagnostics)
    if any(plugin.status == "ERROR" for plugin in data.plugins):
        return _issue(
            "plugin_failed",
            "One or more plugins failed to load or unload.",
            "inspect_plugins",
        )
    if any(plugin.draining for plugin in data.plugins):
        return _issue(
            "plugin_draining",
            "A previous plugin generation is still draining.",
            "wait_for_drain",
        )
    return "ok", []


def _processes(
    data: DiagnosticData, options: DiagnosticOptions
) -> tuple[Status, list[DiagnosticIssue]]:
    assert isinstance(data, ProcessesDiagnostics)
    if not data.observation_available or data.last_monitor_at is None:
        return "unknown", []
    if any(process.last_error_type for process in data.processes):
        return _issue(
            "process_probe_failed",
            "One or more process observations failed.",
            "inspect_logs",
        )
    if any(
        process.observed_running is False and process.expected_status == "RUNNING"
        for process in data.processes
    ):
        return _issue(
            "process_state_mismatch",
            "An expected running process was observed stopped.",
            "inspect_logs",
        )
    return "ok", []


def _transport(
    data: DiagnosticData, options: DiagnosticOptions
) -> tuple[Status, list[DiagnosticIssue]]:
    assert isinstance(data, TransportDiagnostics)
    if (
        data.max_pending_per_client >= data.queue_limit_per_client
        and data.connected_clients
    ):
        return _issue(
            "transport_pressure",
            "WebSocket delivery is under pressure.",
            "inspect_logs",
        )
    return "ok", []


def _state(
    data: DiagnosticData, options: DiagnosticOptions
) -> tuple[Status, list[DiagnosticIssue]]:
    assert isinstance(data, StateDiagnostics)
    if (
        data.oldest_pending_age_seconds is not None
        and data.oldest_pending_age_seconds > options.state_pending_warn_seconds
    ):
        return _issue(
            "state_persistence_delayed",
            "Pending changes have exceeded the configured age threshold.",
            "inspect_storage",
        )
    return "ok", []
