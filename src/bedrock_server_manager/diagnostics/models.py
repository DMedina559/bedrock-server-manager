"""Typed, metadata-only diagnostics shared by HTTP and plugin consumers."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..events.models import EventDiagnostics, EventOptions


class DiagnosticModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class DiagnosticOptions(DiagnosticModel):
    model_config = ConfigDict(
        frozen=True, strict=True, validate_default=True, revalidate_instances="always"
    )
    max_providers: int = Field(default=128, ge=9, le=1000)
    max_providers_per_owner: int = Field(default=8, ge=1, le=50)
    queue_limit: int = Field(default=256, ge=1, le=10000)
    history_limit: int = Field(default=1000, ge=1, le=100000)
    retention_days: int = Field(default=7, ge=1, le=365)
    provider_timeout_seconds: float = Field(default=1, gt=0, le=10)


class DiagnosticRecord(DiagnosticModel):
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
    duration_ms: float = Field(ge=0)


class DiagnosticIssue(DiagnosticModel):
    code: str
    severity: Literal["warning", "error"] = "warning"
    message: str


class RuntimeDiagnostics(DiagnosticModel):
    kind: Literal["runtime"] = "runtime"
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


class EventsDiagnostics(DiagnosticModel):
    kind: Literal["events"] = "events"
    activity: EventDiagnostics
    capacity: EventOptions


class TransportDiagnostics(DiagnosticModel):
    kind: Literal["transport"] = "transport"
    connected_clients: int
    subscriptions: int
    topics: int
    delivery_mode: Literal["direct"] = "direct"
    successful_sends: int = 0
    failed_sends: int = 0


class PluginDiagnostic(DiagnosticModel):
    name: str
    status: str
    generation: int
    active_tasks: int
    draining: bool


class PluginsDiagnostics(DiagnosticModel):
    kind: Literal["plugins"] = "plugins"
    plugins: list[PluginDiagnostic] = Field(default_factory=list)
    total: int = 0
    truncated: bool = False


class TaskDiagnostic(DiagnosticModel):
    id: str
    owner: str | None = None
    status: str
    elapsed_seconds: float | None = None
    error_code: str | None = None


class TasksDiagnostics(DiagnosticModel):
    kind: Literal["tasks"] = "tasks"
    active: int
    tasks: list[TaskDiagnostic] = Field(default_factory=list)
    counts_by_status: dict[str, int]
    accepting: bool


class ProcessDiagnostic(DiagnosticModel):
    server_name: str
    expected_status: str
    observed_running: bool | None = None
    pid: int | None = None


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
    kind: Literal["metrics"] = "metrics"
    last_sample_at: float | None = None
    sample_age_seconds: float | None = None
    interval_seconds: float | None = None


class PluginValues(DiagnosticModel):
    kind: Literal["plugin_values"] = "plugin_values"
    """Explicit numeric observations; plugin secrets and arbitrary dumps are excluded."""

    values: dict[str, float | bool | None] = Field(max_length=50)


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
)


class DiagnosticSection(DiagnosticModel):
    name: str
    owner: str = "application"
    status: Literal["ok", "degraded", "unavailable", "unknown"] = "unknown"
    collected_at: float
    duration_ms: float = 0
    data: DiagnosticData | None = Field(default=None, discriminator="kind")
    issues: list[DiagnosticIssue] = Field(default_factory=list, max_length=20)


class PersistenceDiagnostics(DiagnosticModel):
    queued: int
    max_providers: int = Field(default=128, ge=9, le=1000)
    max_providers_per_owner: int = Field(default=8, ge=1, le=50)
    queue_limit: int
    dropped: int
    write_failures: int
    accepting: bool
    history_limit: int
    retention_days: int


class DiagnosticSnapshot(DiagnosticModel):
    schema_version: Literal[1] = 1
    instance_id: str
    collected_at: float
    counter_scope: Literal["current_instance"] = "current_instance"
    sections: list[DiagnosticSection]
    persistence: PersistenceDiagnostics


class DiagnosticHistory(DiagnosticModel):
    records: list[DiagnosticRecord]
    available: bool
    truncated: bool


class DiagnosticReport(DiagnosticModel):
    snapshot: DiagnosticSnapshot
    history: DiagnosticHistory
