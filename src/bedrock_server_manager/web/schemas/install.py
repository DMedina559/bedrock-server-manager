from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


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
    port: Optional[int] = Field(
        default=None,
        ge=1,
        le=65535,
        description="IPv4 port for the server. Defaults to 19132 if omitted.",
    )
    port_v6: Optional[int] = Field(
        default=None,
        ge=1,
        le=65535,
        description="IPv6 port for the server. Defaults to 19133 if omitted.",
    )
    confirm: Optional[bool] = Field(
        default=False,
        description="If True, confirm overwriting an existing installation.",
    )


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


class AllowlistPlayer(BaseModel):
    """Represents a player entry for the allowlist."""

    name: str = Field(..., description="Player's gamertag.")
    ignoresPlayerLimit: bool = Field(
        default=False,
        description="Whether this player ignores the server's player limit.",
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


class PlayerPermissionItem(BaseModel):
    """Represents a single player's permission data sent from the client."""

    xuid: str
    name: str
    permission_level: str


class PermissionsSetPayload(BaseModel):
    """Request model for setting multiple player permissions."""

    permissions: List[PlayerPermissionItem] = Field(
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
