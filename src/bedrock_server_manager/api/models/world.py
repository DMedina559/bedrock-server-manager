"""Serializable world API request and response contracts."""

from .common import ActionResponse, APIRequest, NonEmptyStr, ServerName, SuccessResponse


class GetWorldNameRequest(APIRequest):
    server_name: ServerName


class GetWorldNameResponse(SuccessResponse):
    world_name: str


class ExportWorldRequest(APIRequest):
    server_name: ServerName
    export_dir: str | None = None


class ExportWorldResponse(ActionResponse):
    export_file: str | None = None
    required_on_success = ("export_file",)


class ImportWorldRequest(APIRequest):
    server_name: ServerName
    selected_file_path: NonEmptyStr
    stop_start_server: bool = True


class ImportWorldResponse(ActionResponse):
    pass


class ResetWorldRequest(APIRequest):
    server_name: ServerName


class ResetWorldResponse(ActionResponse):
    pass
