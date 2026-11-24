"""Serializable permissions API and HTTP contracts."""

from pydantic import Field

from .common import (
    ActionResponse,
    APIRequest,
    APIResponse,
    NonEmptyStr,
    PermissionLevel,
    ServerName,
    SuccessResponse,
)


class PlayerPermission(APIResponse):
    xuid: str
    name: str
    permission_level: str


class PlayerPermissionPayload(APIRequest):
    """Represent a single player's permission data sent from the client."""

    xuid: str
    name: str
    permission_level: PermissionLevel


class PermissionsSetPayload(APIRequest):
    """Request model for setting multiple player permissions."""

    permissions: list[PlayerPermissionPayload] = Field(
        ..., description="List of player permission entries."
    )


class SetPermissionsRequest(APIRequest):
    server_name: ServerName
    xuid: NonEmptyStr
    player_name: NonEmptyStr | None
    permission: PermissionLevel


class SetPermissionsResponse(ActionResponse):
    server_name: ServerName


class GetPermissionsRequest(APIRequest):
    server_name: ServerName


class GetPermissionsResponse(SuccessResponse):
    permissions: list[PlayerPermission]
