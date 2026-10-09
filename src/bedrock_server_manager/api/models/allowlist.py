"""Serializable allowlist API request and response contracts."""

from pydantic import Field

from .common import APIRequest, APIResponse, NonEmptyStr, ServerName, SuccessResponse


class AllowlistPlayer(APIResponse):
    name: NonEmptyStr
    xuid: str | None = None
    ignoresPlayerLimit: bool = False


class AllowlistRemovalDetails(APIResponse):
    removed: list[str]
    not_found: list[str]


class AddToAllowlistRequest(APIRequest):
    server_name: ServerName
    new_players_data: list[AllowlistPlayer]


class AddToAllowlistResponse(SuccessResponse):
    added_count: int = Field(ge=0)


class GetAllowlistRequest(APIRequest):
    server_name: ServerName


class GetAllowlistResponse(SuccessResponse):
    players: list[AllowlistPlayer]


class RemoveFromAllowlistRequest(APIRequest):
    server_name: ServerName
    player_names: list[NonEmptyStr]


class RemoveFromAllowlistResponse(SuccessResponse):
    details: AllowlistRemovalDetails
