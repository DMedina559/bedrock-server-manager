"""Typed, metadata-only diagnostics shared by HTTP and plugin consumers."""

import time
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..events.models import EventDiagnostics, EventOptions, EventSubscriptions
from ..events.operations import OperationActivity


class DiagnosticModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid", allow_inf_nan=False, revalidate_instances="always"
    )


class DiagnosticOptions(DiagnosticModel):
    model_config = ConfigDict(
        frozen=True, strict=True, validate_default=True, revalidate_instances="always"
    )
    max_providers: int = Field(default=128, ge=9, le=1000)
    max_providers_per_owner: int = Field(default=8, ge=1, le=50)
    queue_limit: int = Field(default=256, ge=1, le=10000)
    history_limit: int = Field(default=1000, ge=1, le=100000)
    retention_days: int = Field(default=7, ge=1, le=365)
    stale_after_seconds: float = Field(default=15.0, gt=0, le=3600)
    state_pending_warn_seconds: float = Field(default=60.0, gt=0, le=86400)
    event_record_limit: int = Field(default=20, ge=1, le=100)
    event_detail_limit: int = Field(default=50, ge=1, le=200)
    snapshot_interval_seconds: float | None = Field(default=None, ge=10, le=86400)
    provider_timeout_seconds: float = Field(default=1, gt=0, le=10)


class DiagnosticHealthSample(DiagnosticModel):
    status: Literal["ok", "degraded", "unavailable", "unknown"]
    ready: bool | None
    sections: dict[str, Literal["ok", "degraded", "unavailable", "unknown"]] = Field(
        max_length=1000
    )


class DiagnosticRecord(DiagnosticModel):
    health: DiagnosticHealthSample | None = None
    backend_version: str | None = None
    phase: str | None = None
    id: str
    instance_id: str
    timestamp: float
    subsystem: str = Field(max_length=80, pattern=r"^[\w.:-]+$")
    owner: str | None = Field(default=None, max_length=160)
    operation: str = Field(max_length=160)
    outcome: Literal["completed", "failed", "cancelled"]
    code: str = Field(max_length=80)
    error_type: str | None = Field(default=None, max_length=80)
    operation_id: str | None = Field(default=None, max_length=160)
    correlation_id: str | None = Field(default=None, max_length=160)
    duration_ms: float | None = Field(default=None, ge=0)


class DiagnosticIssue(DiagnosticModel):
    code: str
    severity: Literal["warning", "error"] = "warning"
    message: str
    action: (
        Literal[
            "inspect_logs",
            "inspect_events",
            "inspect_storage",
            "inspect_plugins",
            "wait_for_drain",
            "check_configuration",
        ]
        | None
    ) = None


class RuntimeDiagnostics(DiagnosticModel):
    running_workers: int = 0
    queued_workers: int = 0
    draining_workers: int = 0
    oldest_draining_worker_seconds: float | None = None
    pending_lifecycle_stages: list[str] = Field(default_factory=list)
    kind: Literal["runtime"] = "runtime"
    ready: bool = False
    stage_started_at: float | None = None
    stage_elapsed_seconds: float | None = None
    stage_timeout_seconds: float | None = None
    phase: str
    stage: str | None = None
    pid: int
    uptime_seconds: float
    version: str
    shutdown_requested: bool | None = None
    shutdown_reason: str | None = None
    python_version: str


class StateDiagnostics(DiagnosticModel):
    kind: Literal["state"] = "state"
    epoch: str
    observation_revision: int
    counts: dict[str, int]
    oldest_pending_age_seconds: float | None = None
    pending_changes: dict[str, int]


class StorageDiagnostics(DiagnosticModel):
    kind: Literal["storage"] = "storage"
    attempts: int = 0
    successes: int = 0
    failures: int = 0
    active: int = 0
    last_success_at: float | None = None
    last_duration_ms: float | None = None
    last_error_type: str | None = None
    lock_wait_ms: float | None = None
    total_lock_wait_ms: float = 0
    max_lock_wait_ms: float = 0
    lock_waiters: int = 0
    reload_attempts: int = 0
    reload_successes: int = 0
    reload_failures: int = 0
    reload_active: bool = False
    last_reload_at: float | None = None
    last_reload_duration_ms: float | None = None
    last_reload_error_type: str | None = None


class EventsDiagnostics(DiagnosticModel):
    truncated: bool = False
    kind: Literal["events"] = "events"
    activity: EventDiagnostics
    capacity: EventOptions
    operations: OperationActivity | None = None
    subscriptions: EventSubscriptions = Field(default_factory=EventSubscriptions)


class TransportDiagnostics(DiagnosticModel):
    kind: Literal["transport"] = "transport"
    connected_clients: int
    subscriptions: int
    topics: int
    delivery_mode: Literal["direct"] = "direct"
    successful_sends: int = 0
    failed_sends: int = 0
    accepting: bool = True
    max_pending_per_client: int = 0
    pending_sends: int = 0
    active_sends: int = 0
    queue_limit_per_client: int = 64
    dropped_messages: int = 0
    high_water_mark: int = 0
    send_timeouts: int = 0
    last_send_at: float | None = None
    last_send_duration_ms: float | None = None
    disconnects_by_reason: dict[str, int] = Field(default_factory=dict)


class PluginDiagnostic(DiagnosticModel):
    name: str
    status: str
    generation: int
    active_tasks: int
    managed_tasks: int = 0
    draining: bool
    version: str | None = None
    listeners: int = 0
    workers: int = 0
    diagnostic_providers: int = 0
    last_transition_at: float | None = None
    load_failures: int = 0
    drain_failures: int = 0
    last_drain_duration_ms: float | None = None


class PluginsDiagnostics(DiagnosticModel):
    kind: Literal["plugins"] = "plugins"
    plugins: list[PluginDiagnostic] = Field(default_factory=list)
    total: int = 0
    truncated: bool = False


class TaskDiagnostic(DiagnosticModel):
    name: str = "background_task"
    correlation_id: str | None = None
    cancellation_requested: bool = False
    progress_percent: float | None = Field(default=None, ge=0, le=100)
    id: str
    owner: str | None = None
    status: str
    elapsed_seconds: float | None = None
    error_code: str | None = None


class TasksDiagnostics(DiagnosticModel):
    concurrency_limit: int | None = None
    kind: Literal["tasks"] = "tasks"
    active: int
    tasks: list[TaskDiagnostic] = Field(default_factory=list)
    counts_by_status: dict[str, int]
    accepting: bool
    capacity: int = 100
    oldest_active_seconds: float | None = None


class ProcessDiagnostic(DiagnosticModel):
    server_name: str
    expected_status: str
    observed_running: bool | None = None
    pid: int | None = None
    observed_at: float | None = None
    last_error_type: str | None = None


class ProcessesDiagnostics(DiagnosticModel):
    kind: Literal["processes"] = "processes"
    processes: list[ProcessDiagnostic] = Field(default_factory=list)
    truncated: bool = False
    last_monitor_at: float | None = None
    monitor_failures: int | None = None
    registered: int
    observed_running: int
    observation_available: bool


class MetricsDiagnostics(DiagnosticModel):
    event_loop_lag_ms: float = 0
    recent_max_event_loop_lag_ms: float = 0
    event_loop_lag_threshold_ms: float = 100
    event_loop_lag_breaches: int = 0
    kind: Literal["metrics"] = "metrics"
    last_sample_at: float | None = None
    sample_age_seconds: float | None = None
    interval_seconds: float | None = None
    attempts: int = 0
    successes: int = 0
    failures: int = 0
    missed_intervals: int = 0
    last_duration_ms: float | None = None
    last_error_type: str | None = None
    unavailable_measurements: list[str] = Field(default_factory=list)
    warming_up: bool = True


class BackupsDiagnostics(DiagnosticModel):
    kind: Literal["backups"] = "backups"
    servers: int
    archives: int
    total_bytes: int
    failed: int
    missing_keys: int
    destination_failures: int
    without_backup: int


class SchedulerDiagnostics(DiagnosticModel):
    kind: Literal["scheduler"] = "scheduler"
    running: bool
    schedules: int = Field(ge=0)
    enabled: int = Field(ge=0)
    active_jobs: int = Field(ge=0)
    failed: int = Field(ge=0)
    unavailable: int = Field(ge=0)
    last_tick_at: float | None = None
    tick_age_seconds: float | None = None
    last_error_type: str | None = None
    timezone_database_available: bool = True


class PluginValues(DiagnosticModel):
    """Explicit observations; string dumps and secrets are excluded."""

    model_config = ConfigDict(strict=True, revalidate_instances="always")

    kind: Literal["plugin_values"] = "plugin_values"
    health: Literal["ok", "degraded", "unknown"] = "unknown"
    units: dict[
        str, Literal["count", "seconds", "milliseconds", "bytes", "percent"]
    ] = Field(default_factory=dict, max_length=50)
    values: dict[str, float | bool | None] = Field(max_length=50)

    @model_validator(mode="after")
    def bounded_labels(self):
        if any(not key or len(key) > 80 for key in self.values):
            raise ValueError("Diagnostic labels must contain 1 to 80 characters")
        if set(self.units) - set(self.values):
            raise ValueError("Diagnostic units must describe declared values")
        return self


DiagnosticData = (
    RuntimeDiagnostics
    | StateDiagnostics
    | StorageDiagnostics
    | EventsDiagnostics
    | TransportDiagnostics
    | PluginsDiagnostics
    | TasksDiagnostics
    | ProcessesDiagnostics
    | MetricsDiagnostics
    | PluginValues
    | BackupsDiagnostics
)


class DiagnosticSection(DiagnosticModel):
    name: str
    owner: str = "application"
    status: Literal["ok", "degraded", "unavailable", "unknown"] = "unknown"
    collected_at: float
    observed_at: float | None = None
    last_success_at: float | None = None
    age_seconds: float | None = None
    stale: bool = False
    duration_ms: float = 0
    data: DiagnosticData | None = Field(default=None, discriminator="kind")
    issues: list[DiagnosticIssue] = Field(default_factory=list, max_length=20)


class PersistenceDiagnostics(DiagnosticModel):
    queued: int
    queue_limit: int
    dropped: int
    write_failures: int
    accepting: bool
    history_limit: int
    retention_days: int
    writer_status: Literal["not_started", "running", "failed", "closed"] = "not_started"
    last_success_at: float | None = None
    last_error_type: str | None = None
    read_failures: int = 0
    last_read_success_at: float | None = None
    last_read_error_type: str | None = None


class RegistryDiagnostics(DiagnosticModel):
    registered: int
    pending: int
    max_providers: int
    max_providers_per_owner: int
    owner_limits_scope: Literal["plugins"] = "plugins"
    registered_by_owner: dict[str, int] = Field(default_factory=dict)
    pending_by_owner: dict[str, int] = Field(default_factory=dict)
    failures: int = 0
    timeouts: int = 0
    rejected: int = 0


class DiagnosticFinding(DiagnosticModel):
    subsystem: str
    owner: str
    issue: DiagnosticIssue


class DiagnosticSummary(DiagnosticModel):
    status: Literal["ok", "degraded", "unavailable", "unknown"]
    ready: bool | None
    counts_by_status: dict[str, int]
    findings: list[DiagnosticFinding] = Field(default_factory=list, max_length=100)
    truncated: bool = False


class DiagnosticEnvironment(DiagnosticModel):
    backend_version: str
    frontend_version: str | None = None
    python_version: str
    operating_system: str
    database_dialect: str | None = None
    database_schema_revision: str | None = None


class CollectionDiagnostics(DiagnosticModel):
    status: Literal["ok", "degraded", "unavailable"] = "ok"
    requests: int = 0
    collections: int = 0
    failures: int = 0
    cache_hits: int = 0
    cache_age_seconds: float | None = None
    active: bool = False
    last_duration_ms: float | None = None
    last_success_at: float | None = None
    last_error_type: str | None = None
    periodic_enabled: bool = False
    periodic_status: Literal[
        "disabled", "not_started", "running", "stopped", "failed"
    ] = "disabled"
    last_periodic_success_at: float | None = None
    last_periodic_error_type: str | None = None
    periodic_cycles: int = 0
    periodic_failures: int = 0


class RecentDiagnosticCounts(DiagnosticModel):
    failed: int = 0
    cancelled: int = 0
    timeouts: int = 0


class RecentDiagnosticWindow(DiagnosticModel):
    window_seconds: Literal[300] = 300
    bucket_seconds: Literal[10] = 10
    observed_since: float
    failures: int = 0
    timeouts: int = 0
    cancelled: int = 0
    by_subsystem: dict[str, RecentDiagnosticCounts] = Field(default_factory=dict)


class DiagnosticSnapshot(DiagnosticModel):
    schema_version: Literal[1] = 1
    snapshot_id: str = Field(default_factory=lambda: uuid4().hex)
    instance_id: str
    collected_at: float
    counter_scope: Literal["current_instance"] = "current_instance"
    sections: list[DiagnosticSection] = Field(max_length=1000)
    collection: CollectionDiagnostics = Field(default_factory=CollectionDiagnostics)
    recent: RecentDiagnosticWindow | None = None
    summary: DiagnosticSummary
    registry: RegistryDiagnostics
    environment: DiagnosticEnvironment
    persistence: PersistenceDiagnostics


class DiagnosticHistory(DiagnosticModel):
    records: list[DiagnosticRecord]
    available: bool
    truncated: bool
    next_cursor: str | None = None


class DiagnosticRun(DiagnosticModel):
    instance_id: str
    first_record_at: float
    last_record_at: float
    retained_records: int
    failed_records: int
    cancelled_records: int
    current_instance: bool
    last_observed_phase: str | None = None
    backend_version: str | None = None
    recording_closed: bool | None = None


class DiagnosticRuns(DiagnosticModel):
    runs: list[DiagnosticRun]
    available: bool
    truncated: bool


class DiagnosticReport(DiagnosticModel):
    report_id: str = Field(default_factory=lambda: uuid4().hex)
    generated_at: float = Field(default_factory=time.time)
    runs: DiagnosticRuns | None = None
    snapshot: DiagnosticSnapshot
    history: DiagnosticHistory


class DiagnosticActivity(DiagnosticModel):
    """Global current-instance metadata; no correlation filter is required."""

    scope: Literal["application"] = "application"
    issues: list[DiagnosticIssue] = Field(default_factory=list, max_length=3)
    events: EventDiagnostics | None = None
    operations: OperationActivity | None = None
    subscriptions: EventSubscriptions | None = None
    truncated: bool = False


class DiagnosticTrace(DiagnosticModel):
    operations: OperationActivity | None = None
    operations_available: bool = False
    correlation_id: str
    events: EventDiagnostics | None
    events_available: bool = False
    issues: list[DiagnosticIssue] = Field(default_factory=list, max_length=4)
    tasks: list[TaskDiagnostic]
    tasks_available: bool
    history: DiagnosticHistory
    truncated: bool = False


class DiagnosticChange(DiagnosticModel):
    subsystem: str
    field: str
    before: float | int | bool | str | None
    after: float | int | bool | str | None
    delta: float | None = None
    counter_reset: bool = False


class DiagnosticComparison(DiagnosticModel):
    before_snapshot_id: str
    after_snapshot_id: str
    same_instance: bool
    elapsed_seconds: float | None
    changes: list[DiagnosticChange] = Field(default_factory=list, max_length=200)
    truncated: bool = False
