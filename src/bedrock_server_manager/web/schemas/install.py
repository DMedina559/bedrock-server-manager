from typing import Dict, List, Literal, Optional

from pydantic import Field

from ...api.models.allowlist import GetAllowlistResponse
from ...api.models.common import APIRequest, APIResponse, PermissionLevel, ServerName
from ...api.models.permissions import GetPermissionsResponse
from ...api.models.properties import GetPropertiesResponse
from .base import BaseApiResponse, TaskAcceptedResponse


class InstallServerPayload(APIRequest):
    """Request model for installing a new server."""

    server_name: ServerName = Field(
        ..., min_length=1, max_length=50, description="Name for the new server."
    )
    server_version: str = Field(
        default="LATEST",
        description="Version to install (e.g., 'LATEST', '1.20.10.01', 'CUSTOM').",
    )
    server_zip_path: Optional[str] = Field(
        default=None,
        description="Path to a custom ZIP file, if 'CUSTOM' version is selected.",
    )
    overwrite: Optional[bool] = Field(
        default=False,
        description="If True, confirm overwriting an existing installation.",
    )


class CustomZipsResponse(BaseApiResponse):
    """Response model for custom zips list."""

    custom_zips: List[str]


PropertiesGetResponse = GetPropertiesResponse
AllowlistGetResponse = GetAllowlistResponse
PermissionsGetResponse = GetPermissionsResponse


class PermissionsUpdateResponse(BaseApiResponse):
    """Response model for permissions update."""

    errors: Optional[Dict[str, str]] = None


class InstallConfirmationResponse(APIResponse):
    status: Literal["confirm_needed"] = "confirm_needed"
    message: str
    server_name: str


class InstallationAcceptedResponse(TaskAcceptedResponse):
    server_name: str


InstallServerResponse = InstallConfirmationResponse | InstallationAcceptedResponse


class PropertiesPayload(APIRequest):
    """Request model for updating server.properties."""

    properties: Dict[str, str] = Field(
        ..., description="Dictionary of properties to set."
    )


class AllowlistAddPayload(APIRequest):
    """Request model for adding players to the allowlist."""

    players: List[str] = Field(..., description="List of player gamertags to add.")
    ignoresPlayerLimit: bool = Field(
        default=False, description="Set 'ignoresPlayerLimit' for these players."
    )


class AllowlistRemovePayload(APIRequest):
    """Request model for removing players from the allowlist."""

    players: List[str] = Field(..., description="List of player gamertags to remove.")


class PlayerPermissionPayload(APIRequest):
    """Represents a single player's permission data sent from the client."""

    xuid: str
    name: str
    permission_level: PermissionLevel


class PermissionsSetPayload(APIRequest):
    """Request model for setting multiple player permissions."""

    permissions: List[PlayerPermissionPayload] = Field(
        ..., description="List of player permission entries."
    )
