"""Serializable backup_restore API request and response contracts."""

from pydantic import Field, SecretStr

from ...backups.models import (
    BackupSummary,
    Component,
    ConfigComponent,
    RestorePlan,
    RestoreRecoveryState,
    RestoreResult,
)
from ...results import CleanupResult, ComponentResults
from .common import (
    ActionResponse,
    APIRequest,
    BackupType,
    NonEmptyStr,
    ServerName,
    SuccessResponse,
)


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


class CreateSnapshotResponse(ActionResponse):
    server_name: ServerName
    backup: BackupSummary


class ListSnapshotsRequest(APIRequest):
    server_name: ServerName


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
