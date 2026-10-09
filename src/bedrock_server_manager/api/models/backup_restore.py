"""Serializable backup_restore API request and response contracts."""

from pydantic import Field

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
    pass


class BackupConfigFileRequest(APIRequest):
    server_name: ServerName
    file_to_backup: NonEmptyStr


class BackupConfigFileResponse(ActionResponse):
    pass


class BackupAllRequest(APIRequest):
    server_name: ServerName


class BackupAllResponse(ActionResponse):
    details: dict[str, str | None] = Field(default_factory=dict)


class RestoreAllRequest(APIRequest):
    server_name: ServerName
    stop_start_server: bool = True


class RestoreAllResponse(ActionResponse):
    details: dict[str, str | None] = Field(default_factory=dict)


class RestoreWorldRequest(APIRequest):
    server_name: ServerName
    backup_file_path: NonEmptyStr
    stop_start_server: bool = True


class RestoreWorldResponse(ActionResponse):
    pass


class RestoreConfigFileRequest(APIRequest):
    server_name: ServerName
    backup_file_path: NonEmptyStr
    stop_start_server: bool = True


class RestoreConfigFileResponse(ActionResponse):
    pass


class PruneOldBackupsRequest(APIRequest):
    server_name: ServerName


class PruneOldBackupsResponse(ActionResponse):
    pass
