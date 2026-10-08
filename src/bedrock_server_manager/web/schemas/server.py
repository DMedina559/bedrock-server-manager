from typing import Any, Dict, List, Optional

from pydantic import Field, JsonValue

from ...api.models.common import APIRequest, PlayerInfo, ServerSummary
from ...api.models.player import PlayerScanDetails
from ...api.models.system import ProcessInfo
from .base import BaseApiResponse


class CommandPayload(APIRequest):
    """Request model for sending a command to a server."""

    command: str = Field(
        ..., min_length=1, description="The command to send to the server."
    )


class ServerSettingItemPayload(APIRequest):
    """Request model for a single server setting key-value pair."""

    key: str = Field(
        ...,
        description="The dot-notation key of the setting (e.g., 'settings.autoupdate').",
    )
    value: JsonValue = Field(..., description="The new value for the setting.")


class ServerSettingsResponse(BaseApiResponse):
    """Response model for server settings operations."""

    # status: str = Field(...) -> Inherited
    # message: Optional[str] = None -> Inherited
    settings: Optional[Dict[str, Any]] = None
    setting: Optional[ServerSettingItemPayload] = None


class AddPlayersPayload(APIRequest):
    """Request model for manually adding players to the database.

    Each string in the 'players' list should be in the format "gamertag:xuid".
    """

    players: List[str] = Field(
        ...,
        description='List of player strings, e.g., ["PlayerOne:123xuid", "PlayerTwo:456xuid"]',
    )


ServerSchemaResponse = ServerSummary


# --- Specific Response Models replacing GeneralApiResponse ---


class ServersListResponse(BaseApiResponse):
    """Response model for lists of server data."""

    servers: Optional[List[ServerSummary]] = None


class AppInfoResponse(BaseApiResponse):
    """Response model for app/system info."""

    info: Optional[Dict[str, Any]] = None


class PlayerListResponse(BaseApiResponse):
    """Response model for player lists."""

    players: Optional[List[PlayerInfo]] = None


class AddPlayersResponse(BaseApiResponse):
    """Response model for adding players, typically returns just inherited fields or single item data."""

    details: Optional[PlayerScanDetails] = None
    count: Optional[int] = None


class ServerRunningStatusResponse(BaseApiResponse):
    """Response model for server running status."""

    running: Optional[bool] = None


class ServerProcessInfoResponse(BaseApiResponse):
    """Response model for server process info."""

    process_info: Optional[ProcessInfo] = None
