"""Serializable allowlist API and HTTP contracts."""

from pydantic import Field

from .common import APIRequest, APIResponse, NonEmptyStr, ServerName, SuccessResponse


class AllowlistPlayer(APIResponse):
    name: NonEmptyStr
    xuid: str | None = None
    ignoresPlayerLimit: bool = False


class AllowlistRemovalDetails(APIResponse):
    removed: list[str]
    not_found: list[str]


class AllowlistAddPayload(APIRequest):
    """Request model for adding players to the allowlist."""

    players: list[str] = Field(..., description="List of player gamertags to add.")
    ignoresPlayerLimit: bool = Field(
        default=False, description="Set 'ignoresPlayerLimit' for these players."
    )


class AllowlistRemovePayload(APIRequest):
    """Request model for removing players from the allowlist."""

    players: list[str] = Field(..., description="List of player gamertags to remove.")


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
