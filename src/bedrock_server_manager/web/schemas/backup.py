from typing import Literal, Optional

from pydantic import Field, SecretStr, model_validator

from ...api.models.common import APIRequest
from ...backups.contents import BackupComponents
from ...backups.models import Component, validate_selection_options


class BackupActionPayload(APIRequest):
    """Request model for triggering a backup action."""

    backup_type: str = Field(
        ..., description="Type of backup: 'world', 'config', or 'all'."
    )
    file_to_backup: Optional[str] = Field(
        default=None,
        description="Name of config file if backup_type is 'config' (e.g., 'server.properties').",
    )


class RestoreActionPayload(APIRequest):
    """Request model for triggering a restore action."""

    restore_type: str = Field(
        ...,
        description="Type of restore: 'world', 'properties', 'allowlist', 'permissions', or 'all'.",
    )
    backup_file: Optional[str] = Field(
        default=None,
        description="Name of the backup file (basename) to restore from (required if not 'all').",
    )


class SnapshotCreatePayload(APIRequest):
    encrypted: bool | None = None
    mode: Literal["world", "selected", "full"] | None = None
    components: BackupComponents | None = None

    _validate_selection = model_validator(mode="after")(validate_selection_options)


class SnapshotInspectPayload(APIRequest):
    recovery_key: SecretStr | None = None


class SnapshotPlanPayload(SnapshotInspectPayload):
    components: list[Component]


class SnapshotRestorePayload(SnapshotPlanPayload):
    token: str
    restart: bool = True
    stop_running: bool = True


class SnapshotManagePayload(SnapshotInspectPayload):
    action: Literal["verify", "pin", "unpin", "copy", "test_key", "annotate", "drill"]
    destination: str | None = None
    label: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None, max_length=2000)


class SnapshotCopyPayload(SnapshotInspectPayload):
    target_server: str
    target_version: str = "LATEST"
    server_port: int = Field(ge=1, le=65535)
    server_portv6: int = Field(ge=1, le=65535)


class DestinationCleanupPayload(APIRequest):
    token: str | None = None
