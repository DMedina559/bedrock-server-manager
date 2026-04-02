from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .base import BaseApiResponse


class InstallServerPayload(BaseModel):
    """Request model for installing a new server."""

    server_name: str = Field(
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


class PropertiesGetResponse(BaseApiResponse):
    """Response model for server properties."""

    properties: Dict[str, Any]


class AllowlistGetResponse(BaseApiResponse):
    """Response model for server allowlist."""

    allowlist: List[Dict[str, Any]]


class PermissionsGetResponse(BaseApiResponse):
    """Response model for server permissions."""

    permissions: List[Dict[str, Any]]


class PermissionsUpdateResponse(BaseApiResponse):
    """Response model for permissions update."""

    errors: Optional[Dict[str, str]] = None


class InstallServerResponse(BaseModel):
    """Response model for server installation requests."""

    status: str = Field(
        ...,
        description="Status of the installation ('success', 'confirm_needed', 'pending').",
    )
    message: str = Field(..., description="Descriptive message about the operation.")
    server_name: Optional[str] = Field(
        default=None,
        description="Name of the server, especially if confirmation is needed.",
    )
    task_id: Optional[str] = Field(
        default=None, description="Task ID for background installation."
    )


class PropertiesPayload(BaseModel):
    """Request model for updating server.properties."""

    properties: Dict[str, Any] = Field(
        ..., description="Dictionary of properties to set."
    )


class AllowlistAddPayload(BaseModel):
    """Request model for adding players to the allowlist."""

    players: List[str] = Field(..., description="List of player gamertags to add.")
    ignoresPlayerLimit: bool = Field(
        default=False, description="Set 'ignoresPlayerLimit' for these players."
    )


class AllowlistRemovePayload(BaseModel):
    """Request model for removing players from the allowlist."""

    players: List[str] = Field(..., description="List of player gamertags to remove.")


class PlayerPermissionPayload(BaseModel):
    """Represents a single player's permission data sent from the client."""

    xuid: str
    name: str
    permission_level: str


class PermissionsSetPayload(BaseModel):
    """Request model for setting multiple player permissions."""

    permissions: List[PlayerPermissionPayload] = Field(
        ..., description="List of player permission entries."
    )


class ServiceUpdatePayload(BaseModel):
    """Request model for updating server-specific service settings."""

    autoupdate: Optional[bool] = Field(
        default=None, description="Enable/disable automatic updates for the server."
    )
    autostart: Optional[bool] = Field(
        default=None, description="Enable/disable service autostart for the server."
    )
