"""Versioned portable backup contracts."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue

ConfigComponent = Literal["server.properties", "allowlist.json", "permissions.json"]

Component = Literal[
    "world",
    "server.properties",
    "allowlist.json",
    "permissions.json",
    "script_config",
    "bsm_settings",
]
COMPONENTS: tuple[Component, ...] = (
    "world",
    "server.properties",
    "allowlist.json",
    "permissions.json",
    "script_config",
    "bsm_settings",
)
PREFIXES = {
    "world": "world",
    "server.properties": "config/server.properties",
    "allowlist.json": "config/allowlist.json",
    "permissions.json": "config/permissions.json",
    "script_config": "server-config",
    "bsm_settings": "bsm/server-settings.json",
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
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class BackupManifest(Record):
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
    reason: Literal["manual", "pre_start", "pre_update", "pre_restore"] = "manual"
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
    status: Literal["pending", "completed", "failed"]
    completed_at: str | None = None
    error: str | None = None


class BackupSummary(Record):
    backup_id: str
    filename: str
    size: int
    encrypted: bool
    key_id: str | None = None
    verification: BackupVerification = Field(default_factory=BackupVerification)
    pinned: bool = False
    protected_until: str | None = None
    purpose: str | None = None
    copies: dict[str, BackupCopy] = Field(default_factory=dict)
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
    verification_interval_hours: int
