"""Serializable player API request and response contracts."""

from typing import Annotated

from pydantic import Field

from .common import APIRequest, APIResponse, NonEmptyStr, PlayerInfo, SuccessResponse


class PlayerScanError(APIResponse):
    server: str
    error: str


class PlayerScanDetails(APIResponse):
    total_entries_in_logs: int = Field(ge=0)
    unique_players_submitted_for_saving: int = Field(ge=0)
    actually_saved_or_updated_in_db: int = Field(ge=0)
    scan_errors: list[PlayerScanError]


class AddPlayersManuallyRequest(APIRequest):
    player_strings: Annotated[list[NonEmptyStr], Field(min_length=1)]


class AddPlayersManuallyResponse(SuccessResponse):
    count: int = Field(ge=0)


class GetAllKnownPlayersRequest(APIRequest):
    pass


class GetAllKnownPlayersResponse(SuccessResponse):
    players: list[PlayerInfo]


class ScanAndUpdatePlayerDbRequest(APIRequest):
    pass


class ScanAndUpdatePlayerDbResponse(SuccessResponse):
    details: PlayerScanDetails
