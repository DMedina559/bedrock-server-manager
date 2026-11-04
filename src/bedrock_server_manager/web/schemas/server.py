from typing import Dict, List, Optional

from pydantic import Field, JsonValue

from ...api.models.common import APIRequest, ServerSummary, StateRevision
from ...contracts import NonEmptyStr, ResourceFailure
from .base import BaseApiResponse


class CommandPayload(APIRequest):
    """Request model for sending a command to a server."""

    command: str = Field(
        ..., min_length=1, description="The command to send to the server."
    )


class ServerSettingItemPayload(APIRequest):
    """Request model for a single server setting key-value pair."""

    key: NonEmptyStr = Field(
        ...,
        description="The dot-notation key of the setting (e.g., 'settings.autoupdate').",
    )
    value: JsonValue = Field(..., description="The new value for the setting.")


class ServerSettingsResponse(BaseApiResponse):
    """Response model for server settings operations."""

    settings: Optional[Dict[str, JsonValue]] = None
    setting: Optional[ServerSettingItemPayload] = None


class AddPlayersPayload(APIRequest):
    """Request model for manually adding players to the database.

    Each string in the 'players' list should be in the format "gamertag:xuid".
    """

    players: List[NonEmptyStr] = Field(
        ...,
        min_length=1,
        description='List of player strings, e.g., ["PlayerOne:123xuid", "PlayerTwo:456xuid"]',
    )


class ServersListResponse(BaseApiResponse, StateRevision):
    """Response model for lists of server data."""

    errors: list[ResourceFailure] = Field(default_factory=list)
    servers: Optional[List[ServerSummary]] = None


class AppInfoResponse(BaseApiResponse):
    """Response model for app/system info."""

    info: Optional[Dict[str, JsonValue]] = None


class ServerRunningStatusResponse(BaseApiResponse, StateRevision):
    """Response model for server running status."""

    running: Optional[bool] = None
