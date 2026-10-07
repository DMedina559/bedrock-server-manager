"""Serializable install API request and response contracts."""

from .common import ActionResponse, APIRequest, NonEmptyStr, ServerName


class InstallNewServerRequest(APIRequest):
    server_name: ServerName
    target_version: NonEmptyStr = "LATEST"
    server_zip_path: str | None = None


class InstallNewServerResponse(ActionResponse):
    version: str | None = None
    required_on_success = ("version",)


class UpdateServerRequest(APIRequest):
    server_name: ServerName
    send_message: bool = True


class UpdateServerResponse(ActionResponse):
    updated: bool | None = None
    new_version: str | None = None
    required_on_success = ("updated",)
