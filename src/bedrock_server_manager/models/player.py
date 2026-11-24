"""Serializable player API and HTTP contracts."""

from typing import Annotated

from pydantic import Field

from .common import (
    APIRequest,
    NonEmptyStr,
    PartialResponse,
    PlayerInfo,
    PlayerScanDetails,
    PlayerScanError,
    SuccessResponse,
)


class AddPlayersPayload(APIRequest):
    """Request model for manually adding players to the database.

    Each string in the 'players' list should be in the format "gamertag:xuid".
    """

    players: list[NonEmptyStr] = Field(
        ...,
        min_length=1,
        description='List of player strings, e.g., ["PlayerOne:123xuid", "PlayerTwo:456xuid"]',
    )


class AddPlayersManuallyRequest(APIRequest):
    player_strings: Annotated[list[NonEmptyStr], Field(min_length=1)]


class AddPlayersManuallyResponse(SuccessResponse):
    count: int = Field(ge=0)
    submitted_count: int = Field(ge=0)
    parsed_count: int = Field(ge=0)
    unique_count: int = Field(ge=0)


class GetAllKnownPlayersRequest(APIRequest):
    pass


class GetAllKnownPlayersResponse(SuccessResponse):
    players: list[PlayerInfo]


class ScanAndUpdatePlayerDbRequest(APIRequest):
    pass


class ScanAndUpdatePlayerDbResponse(PartialResponse):
    details: PlayerScanDetails


__all__ = [
    "PlayerScanDetails",
    "PlayerScanError",
    "AddPlayersPayload",
    "AddPlayersManuallyRequest",
    "AddPlayersManuallyResponse",
    "GetAllKnownPlayersRequest",
    "GetAllKnownPlayersResponse",
    "ScanAndUpdatePlayerDbRequest",
    "ScanAndUpdatePlayerDbResponse",
]
