"""Serializable permissions API request and response contracts."""

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


class SetPermissionsRequest(APIRequest):
    server_name: ServerName
    xuid: NonEmptyStr
    player_name: NonEmptyStr | None
    permission: PermissionLevel


class SetPermissionsResponse(ActionResponse):
    pass


class GetPermissionsRequest(APIRequest):
    server_name: ServerName


class GetPermissionsResponse(SuccessResponse):
    permissions: list[PlayerPermission]
