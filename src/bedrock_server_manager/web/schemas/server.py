from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .base import BaseApiResponse


class CommandPayload(BaseModel):
    """Request model for sending a command to a server."""

    command: str = Field(
        ..., min_length=1, description="The command to send to the server."
    )


class ServerSettingItemPayload(BaseModel):
    """Request model for a single server setting key-value pair."""

    key: str = Field(
        ...,
        description="The dot-notation key of the setting (e.g., 'settings.autoupdate').",
    )
    value: Any = Field(..., description="The new value for the setting.")


class ServerSettingsResponse(BaseApiResponse):
    """Response model for server settings operations."""

    # status: str = Field(...) -> Inherited
    # message: Optional[str] = None -> Inherited
    settings: Optional[Dict[str, Any]] = None
    setting: Optional[ServerSettingItemPayload] = None


class AddPlayersPayload(BaseModel):
    """Request model for manually adding players to the database.

    Each string in the 'players' list should be in the format "gamertag:xuid".
    """

    players: List[str] = Field(
        ...,
        description='List of player strings, e.g., ["PlayerOne:123xuid", "PlayerTwo:456xuid"]',
    )


class ServerSchemaResponse(BaseModel):
    """
    Schema representing server information in lists.

    Attributes:
        name (str): The server's name.
        status (str): The server's status (e.g., "Running", "Stopped").
        version (str): The installed version of the server.
        player_count (int): The number of players currently online.
    """

    name: str
    status: str
    version: str
    player_count: int


# --- Specific Response Models replacing GeneralApiResponse ---


class ServersListResponse(BaseApiResponse):
    """Response model for lists of server data."""

    servers: Optional[List[ServerSchemaResponse]] = None


class AppInfoResponse(BaseApiResponse):
    """Response model for app/system info."""

    info: Optional[Dict[str, Any]] = None


class PlayerListResponse(BaseApiResponse):
    """Response model for player lists."""

    players: Optional[List[Dict[str, Any]]] = None


class AddPlayersResponse(BaseApiResponse):
    """Response model for adding players, typically returns just inherited fields or single item data."""

    data: Optional[Dict[str, Any]] = None


class ThemeListResponse(BaseApiResponse):
    """Response model for theme lists."""

    themes: Optional[List[str]] = None


class ServerRunningStatusResponse(BaseApiResponse):
    """Response model for server running status."""

    data: Optional[Dict[str, bool]] = None


class ServerConfigStatusResponse(BaseApiResponse):
    """Response model for server config status."""

    data: Optional[Dict[str, str]] = None


class ServerVersionResponse(BaseApiResponse):
    """Response model for server installed version."""

    data: Optional[Dict[str, str]] = None


class ServerProcessInfoResponse(BaseApiResponse):
    """Response model for server process info."""

    data: Optional[Dict[str, Any]] = None
