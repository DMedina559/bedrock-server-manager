"""Versioned portable backup contracts."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from .contents import DEFAULT_COMPONENTS, SERVER_PACK_COMPONENTS, BackupMode

ConfigComponent = Literal["server.properties", "allowlist.json", "permissions.json"]

Component = Literal[
    "server_directory",
    "world",
    "server.properties",
    "allowlist.json",
    "permissions.json",
    "script_config",
    "bsm_settings",
    "behavior_packs",
    "resource_packs",
    "development_behavior_packs",
    "development_resource_packs",
]
BASE_COMPONENTS: tuple[Component, ...] = DEFAULT_COMPONENTS
PACK_COMPONENTS: tuple[Component, ...] = SERVER_PACK_COMPONENTS
COMPONENTS = BASE_COMPONENTS + PACK_COMPONENTS + ("server_directory",)
DIRECTORY_COMPONENTS = ("server_directory", "world", "script_config", *PACK_COMPONENTS)

PREFIXES = {
    "server_directory": "server-directory",
    "world": "world",
    "server.properties": "config/server.properties",
    "allowlist.json": "config/allowlist.json",
    "permissions.json": "config/permissions.json",
    "script_config": "server-config",
    "bsm_settings": "bsm/server-settings.json",
    **{name: "packs/" + name for name in PACK_COMPONENTS},
}


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ServerSettingsExport(Record):
    schema_version: Literal[1] = 1
    autostart: bool
    autoupdate: bool
    target_version: str
    custom: dict[str, JsonValue] = Field(default_factory=dict)


class BackupFile(Record):
    path: str
    component: Component
    size: int = Field(ge=0)
    executable: bool = False
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class BackupManifest(Record):
    source_platform: str | None = None
    source_architecture: str | None = None
    mode: BackupMode | None = None
    selected_components: list[Component] | None = None
    format: Literal["bsmbackup"] = "bsmbackup"
    format_version: Literal[1] = 1
    backup_id: UUID
    created_at: datetime
    capture_started_at: datetime
    capture_finished_at: datetime
    bsm_version: str
    bedrock_version: str
    source_server: str
    source_world: str
    capture_method: Literal["offline", "live"]
    reason: Literal["manual", "pre_start", "pre_update", "pre_restore", "scheduled"] = (
        "manual"
    )
    components: dict[Component, Literal["included", "absent"]]
    files: list[BackupFile]
    directories: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class BackupHeader(Record):
    format: Literal["bsmbackup"] = "bsmbackup"
    container_version: Literal[1] = 1
    encrypted: bool = False
    key_id: str | None = None


class BackupVerification(Record):
    verified_at: str | None = None
    status: Literal["unverified", "verified", "failed"] = "unverified"
    error: str | None = None


class BackupCopy(Record):
    status: Literal["pending", "completed", "failed", "pruned"]
    completed_at: str | None = None
    error: str | None = None
    attempts: int = 0
    next_retry_at: str | None = None


class BackupSummary(Record):
    backup_id: str
    filename: str
    created_at: str | None = None
    drill: dict[str, JsonValue] | None = None
    size: int
    encrypted: bool
    key_id: str | None = None
    verification: BackupVerification = Field(default_factory=BackupVerification)
    stage_durations_ms: dict[str, float] = Field(default_factory=dict)
    pinned: bool = False
    protected_until: str | None = None
    purpose: str | None = None
    copies: dict[str, BackupCopy] = Field(default_factory=dict)
    label: str = ""
    notes: str = ""
    origin: Literal["captured", "imported"] = "captured"
    manifest: BackupManifest | None = None
    error: str | None = None


class RestoreFileChange(Record):
    component: Component
    path: str
    action: Literal["added", "replaced", "removed"]


class RestoreValueChange(Record):
    component: Component
    key: str
    before: str | None
    after: str | None


class RestoreVolume(Record):
    roles: list[str]
    required_bytes: int
    available_bytes: int
    sufficient: bool


class RestorePlan(Record):
    backup_id: str
    token: str
    components: list[Component]
    destinations: dict[Component, str]
    warnings: list[str]
    changes: list[RestoreFileChange] = Field(default_factory=list)
    changes_truncated: bool = False
    change_counts: dict[str, int] = Field(default_factory=dict)
    setting_changes: list[RestoreValueChange] = Field(default_factory=list)
    safety_backup: bool = True
    required_bytes: int
    volumes: list[RestoreVolume] = Field(default_factory=list)
    sufficient_space: bool = True
    dry_run: bool = False
    checked_files: int = 0


class RestoreResult(Record):
    safety_backup_id: str | None = None
    restored: list[Component]
    committed: bool = True
    restarted: bool = False
    restart_error: str | None = None
    cleanup_warning: str | None = None


class RestoreRecoveryState(Record):
    active: bool
    committed: bool | None = None
    error: str | None = None


class BackupHealth(Record):
    count: int
    total_bytes: int
    last_success_at: str | None = None
    last_verified_at: str | None = None
    last_failure_at: str | None = None
    last_error: str | None = None
    unverified_count: int = 0
    failed_count: int = 0
    missing_key_ids: list[str] = Field(default_factory=list)
    older_key_ids: list[str] = Field(default_factory=list)
    destination_failures: int = 0
    schedule: dict[str, JsonValue] | None = None
    verification_interval_hours: int
    readiness: Literal["ready", "attention", "unavailable"] = "unavailable"
    readiness_reasons: list[str] = Field(default_factory=list)
    recovery_backup_id: str | None = None
    drill: dict[str, JsonValue] | None = None
    destinations: dict[str, JsonValue] = Field(default_factory=dict)
    alerts: list[dict[str, JsonValue]] = Field(default_factory=list)


class DestinationCleanupPlan(Record):
    destination: str
    token: str
    delete: list[str]
    retain: list[str]
    reclaim_bytes: int
    available_bytes: int
    warnings: list[str] = Field(default_factory=list)
    applied: bool = False


class RecoveryReportReview(Record):
    recorded_at: str
    archive_reference: str
    components: list[Component]
    dry_run: bool
    checked_files: int
    change_counts: dict[str, int]
    sufficient_space: bool
    volumes: list[RestoreVolume]


class RecoveryReportOutcome(Record):
    recorded_at: str
    archive_reference: str
    status: Literal["completed", "failed", "cancelled"]
    committed: bool | None = None
    components: list[Component]
    restarted: bool = False
    restart_failed: bool = False
    cleanup_needed: bool = False


class RecoveryReportArchive(Record):
    archive_reference: str
    encrypted: bool
    key_available: bool
    verification_status: Literal["unverified", "verified", "failed"]
    verified_at: str | None = None
    copies_completed: int
    copies_failed: int


class RecoveryReportDrill(Record):
    archive_reference: str
    status: Literal["passed", "failed", "running"]
    checked_at: str | None = None
    checked_files: int = 0


class RecoveryReport(Record):
    report_version: Literal[1] = 1
    generated_at: str
    readiness: Literal["ready", "attention", "unavailable"]
    archive_count: int
    archives_omitted: int
    missing_key_count: int
    destination_failures: int
    recovery_pending: bool
    archives: list[RecoveryReportArchive]
    last_review: RecoveryReportReview | None = None
    last_restore: RecoveryReportOutcome | None = None
    last_drill: RecoveryReportDrill | None = None


def validate_selection_options(value):
    """Validate explicit content overrides before a background task is accepted."""
    mode = value.mode
    components = value.components
    if components is not None and mode not in (None, "selected"):
        raise ValueError("Components are only supported in selected mode")
    return value
