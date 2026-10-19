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
    reason: Literal["manual", "pre_start", "pre_update"] = "manual"
    components: dict[Component, Literal["included", "absent"]]
    files: list[BackupFile]
    directories: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class BackupHeader(Record):
    format: Literal["bsmbackup"] = "bsmbackup"
    container_version: Literal[1] = 1
    encrypted: bool = False
    key_id: str | None = None


class BackupSummary(Record):
    backup_id: str
    filename: str
    size: int
    encrypted: bool
    key_id: str | None = None
    manifest: BackupManifest | None = None
    error: str | None = None


class RestorePlan(Record):
    backup_id: str
    token: str
    components: list[Component]
    destinations: dict[Component, str]
    warnings: list[str]
    required_bytes: int


class RestoreResult(Record):
    restored: list[Component]
    committed: bool = True
    restarted: bool = False
    restart_error: str | None = None
    cleanup_warning: str | None = None


class RestoreRecoveryState(Record):
    active: bool
    committed: bool | None = None
    error: str | None = None
