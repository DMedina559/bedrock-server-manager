"""Serializable backup_restore API and HTTP contracts."""

from typing import Literal

from pydantic import Field, SecretStr, model_validator

from ..backups.contents import BackupComponents
from ..backups.models import (
    BackupHealth,
    BackupKeyInfo,
    BackupKeysInfo,
    BackupSummary,
    Component,
    ConfigComponent,
    DestinationCleanupPlan,
    RecoveryReport,
    RestorePlan,
    RestoreRecoveryState,
    RestoreResult,
    validate_selection_options,
)
from .common import (
    ActionResponse,
    APIRequest,
    BackupType,
    CleanupResult,
    ComponentResults,
    NonEmptyStr,
    ServerName,
    SuccessResponse,
)


class BackupActionPayload(APIRequest):
    """Request model for triggering a backup action."""

    backup_type: str = Field(
        ..., description="Type of backup: 'world', 'config', or 'all'."
    )
    file_to_backup: str | None = Field(
        default=None,
        description="Name of config file if backup_type is 'config' (e.g., 'server.properties').",
    )


class RestoreActionPayload(APIRequest):
    """Request model for triggering a restore action."""

    restore_type: str = Field(
        ...,
        description="Type of restore: 'world', 'properties', 'allowlist', 'permissions', or 'all'.",
    )
    backup_file: str | None = Field(
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


class ListBackupFilesRequest(APIRequest):
    server_name: ServerName
    backup_type: BackupType


class ListBackupFilesResponse(SuccessResponse):
    backups: list[str] | dict[str, list[str]]


class BackupWorldRequest(APIRequest):
    server_name: ServerName


class BackupWorldResponse(ActionResponse):
    server_name: ServerName


class BackupConfigFileRequest(APIRequest):
    server_name: ServerName
    file_to_backup: NonEmptyStr


class BackupConfigFileResponse(ActionResponse):
    server_name: ServerName


class BackupAllRequest(APIRequest):
    server_name: ServerName
    mode: Literal["world", "selected", "full"] | None = Field(
        default=None, exclude=True
    )
    components: BackupComponents | None = Field(default=None, exclude=True)
    encrypted: bool | None = Field(default=None, exclude=True)

    _validate_selection = model_validator(mode="after")(validate_selection_options)


class BackupAllResponse(ActionResponse):
    server_name: ServerName
    details: ComponentResults = Field(default_factory=ComponentResults)


class RestoreAllRequest(APIRequest):
    server_name: ServerName
    stop_start_server: bool = True


class RestoreAllResponse(ActionResponse):
    server_name: ServerName
    details: ComponentResults = Field(default_factory=ComponentResults)


class RestoreWorldRequest(APIRequest):
    server_name: ServerName
    backup_file_path: NonEmptyStr
    stop_start_server: bool = True


class RestoreWorldResponse(ActionResponse):
    server_name: ServerName


class RestoreConfigFileRequest(APIRequest):
    server_name: ServerName
    backup_file_path: NonEmptyStr
    component: ConfigComponent | None = None
    stop_start_server: bool = True


class RestoreConfigFileResponse(ActionResponse):
    server_name: ServerName


class PruneOldBackupsRequest(APIRequest):
    server_name: ServerName


class PruneOldBackupsResponse(ActionResponse):
    server_name: ServerName
    result: CleanupResult = Field(default_factory=CleanupResult)


# Unified archive operations. Legacy contracts remain readable during migration.


class CreateSnapshotRequest(APIRequest):
    server_name: ServerName
    encrypted: bool | None = None
    mode: Literal["world", "selected", "full"] | None = Field(
        default=None, exclude=True
    )
    components: BackupComponents | None = Field(default=None, exclude=True)
    purpose: Literal["manual", "scheduled"] = "manual"
    schedule_slot: str | None = Field(default=None, max_length=128)

    _validate_selection = model_validator(mode="after")(validate_selection_options)


class CreateSnapshotResponse(ActionResponse):
    server_name: ServerName
    backup: BackupSummary


class ListSnapshotsRequest(APIRequest):
    server_name: ServerName


class SnapshotReuseRequest(ListSnapshotsRequest):
    mode: Literal["world", "selected", "full"] | None = Field(
        default=None, exclude=True
    )
    components: BackupComponents | None = Field(default=None, exclude=True)

    _validate_selection = model_validator(mode="after")(validate_selection_options)


class ListSnapshotsResponse(SuccessResponse):
    backups: list[BackupSummary]


class InspectSnapshotRequest(APIRequest):
    server_name: ServerName
    backup_id: NonEmptyStr
    recovery_key: SecretStr | None = Field(default=None, exclude=True)


class InspectSnapshotResponse(SuccessResponse):
    backup: BackupSummary


class PlanSnapshotRestoreRequest(InspectSnapshotRequest):
    components: list[Component] = Field(min_length=1)


class PlanSnapshotRestoreResponse(SuccessResponse):
    plan: RestorePlan


class RestoreSnapshotRequest(PlanSnapshotRestoreRequest):
    token: NonEmptyStr
    restart: bool = True
    stop_running: bool = True


class RestoreSnapshotResponse(ActionResponse):
    server_name: ServerName
    result: RestoreResult


class RestoreRecoveryResponse(SuccessResponse):
    recovery: RestoreRecoveryState


class BackupHealthResponse(SuccessResponse):
    health: BackupHealth


class ManageSnapshotRequest(InspectSnapshotRequest):
    action: Literal[
        "verify", "pin", "unpin", "copy", "test_key", "annotate", "drill", "delete"
    ]
    destination: str | None = None
    label: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None, max_length=2000)


class DeleteSnapshotRequest(APIRequest):
    server_name: ServerName
    backup_id: NonEmptyStr


class ManageSnapshotResponse(SuccessResponse):
    message: str


class PrepareBackupCopyRequest(InspectSnapshotRequest):
    target_server: ServerName
    target_version: NonEmptyStr = "LATEST"
    server_port: int = Field(ge=1, le=65535)
    server_portv6: int = Field(ge=1, le=65535)


class PrepareBackupCopyResponse(SuccessResponse):
    server_name: str
    backup_id: str
    message: str


class SnapshotReuseResponse(SuccessResponse):
    reusable: bool


class CleanupBackupDestinationRequest(ListSnapshotsRequest):
    destination: NonEmptyStr
    token: str | None = None


class CleanupBackupDestinationResponse(SuccessResponse):
    plan: DestinationCleanupPlan


class RecoveryReportResponse(SuccessResponse):
    report: RecoveryReport


__all__ = [
    "BackupActionPayload",
    "RestoreActionPayload",
    "SnapshotCreatePayload",
    "SnapshotInspectPayload",
    "SnapshotPlanPayload",
    "SnapshotRestorePayload",
    "SnapshotManagePayload",
    "SnapshotCopyPayload",
    "DestinationCleanupPayload",
    "BackupKeyInfo",
    "BackupKeysInfo",
    "ListBackupFilesRequest",
    "ListBackupFilesResponse",
    "BackupWorldRequest",
    "BackupWorldResponse",
    "BackupConfigFileRequest",
    "BackupConfigFileResponse",
    "BackupAllRequest",
    "BackupAllResponse",
    "RestoreAllRequest",
    "RestoreAllResponse",
    "RestoreWorldRequest",
    "RestoreWorldResponse",
    "RestoreConfigFileRequest",
    "RestoreConfigFileResponse",
    "PruneOldBackupsRequest",
    "PruneOldBackupsResponse",
    "CreateSnapshotRequest",
    "CreateSnapshotResponse",
    "ListSnapshotsRequest",
    "SnapshotReuseRequest",
    "ListSnapshotsResponse",
    "InspectSnapshotRequest",
    "InspectSnapshotResponse",
    "PlanSnapshotRestoreRequest",
    "PlanSnapshotRestoreResponse",
    "RestoreSnapshotRequest",
    "RestoreSnapshotResponse",
    "RestoreRecoveryResponse",
    "BackupHealthResponse",
    "ManageSnapshotRequest",
    "DeleteSnapshotRequest",
    "ManageSnapshotResponse",
    "PrepareBackupCopyRequest",
    "PrepareBackupCopyResponse",
    "SnapshotReuseResponse",
    "CleanupBackupDestinationRequest",
    "CleanupBackupDestinationResponse",
    "RecoveryReportResponse",
]
