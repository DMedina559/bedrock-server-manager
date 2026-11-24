"""Serializable ban API and HTTP contracts."""

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


class BanAddRequest(APIRequest):
    player_name: NonEmptyStr
    xuid: NonEmptyStr
    reason: str | None = None


class BanRemoveRequest(APIRequest):
    xuid: NonEmptyStr


class AddServerBanRequest(BanAddRequest):
    server_name: ServerName


class AddServerBanResponse(ActionResponse):
    server_name: ServerName


class RemoveServerBanRequest(BanRemoveRequest):
    server_name: ServerName


class RemoveServerBanResponse(ActionResponse):
    server_name: ServerName


class GetServerBansRequest(APIRequest):
    server_name: ServerName


class GetServerBansResponse(SuccessResponse):
    bans: list[BanInfo]
