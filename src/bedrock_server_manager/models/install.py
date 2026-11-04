"""Serializable install API and HTTP contracts."""

from pydantic import Field

from .common import ActionResponse, APIRequest, NonEmptyStr, ServerName


class InstallServerPayload(APIRequest):
    """Request model for installing a new server."""

    server_name: ServerName = Field(
        ..., min_length=1, max_length=50, description="Name for the new server."
    )
    server_version: str = Field(
        default="LATEST",
        description="Version to install (e.g., 'LATEST', '1.20.10.01', 'CUSTOM').",
    )
    server_zip_path: str | None = Field(
        default=None,
        description="Path to a custom ZIP file, if 'CUSTOM' version is selected.",
    )
    overwrite: bool | None = Field(
        default=False,
        description="If True, confirm overwriting an existing installation.",
    )


class InstallNewServerRequest(APIRequest):
    server_name: ServerName
    target_version: NonEmptyStr = "LATEST"
    server_zip_path: str | None = None


class InstallNewServerResponse(ActionResponse):
    server_name: ServerName
    version: str | None = None
    required_on_success = ("version",)


class UpdateServerRequest(APIRequest):
    server_name: ServerName
    send_message: bool = True


class UpdateServerResponse(ActionResponse):
    server_name: ServerName
    updated: bool | None = None
    new_version: str | None = None
    required_on_success = ("updated",)
