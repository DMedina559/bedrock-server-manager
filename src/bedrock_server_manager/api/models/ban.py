"""Serializable ban API request and response contracts."""

from .common import (
    ActionResponse,
    APIRequest,
    APIResponse,
    NonEmptyStr,
    ServerName,
    SuccessResponse,
)


class BanInfo(APIResponse):
    player_name: str
    xuid: str
    reason: str | None = None
    banned_at: str | None = None


class AddServerBanRequest(APIRequest):
    server_name: ServerName
    player_name: NonEmptyStr
    xuid: NonEmptyStr
    reason: str | None = None


class AddServerBanResponse(ActionResponse):
    pass


class RemoveServerBanRequest(APIRequest):
    server_name: ServerName
    xuid: NonEmptyStr


class RemoveServerBanResponse(ActionResponse):
    pass


class GetServerBansRequest(APIRequest):
    server_name: ServerName


class GetServerBansResponse(SuccessResponse):
    bans: list[BanInfo]
