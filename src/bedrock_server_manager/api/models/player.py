"""Serializable player API request and response contracts."""

from typing import Annotated

from pydantic import Field

from ...contracts import PlayerScanDetails as PlayerScanDetails
from ...contracts import PlayerScanError as PlayerScanError
from .common import (
    APIRequest,
    NonEmptyStr,
    PartialResponse,
    PlayerInfo,
    SuccessResponse,
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
    "AddPlayersManuallyRequest",
    "AddPlayersManuallyResponse",
    "GetAllKnownPlayersRequest",
    "GetAllKnownPlayersResponse",
    "ScanAndUpdatePlayerDbRequest",
    "ScanAndUpdatePlayerDbResponse",
]
