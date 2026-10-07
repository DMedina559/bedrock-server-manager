"""Request and response contracts for server lifecycle operations."""

from typing import Annotated, Literal

from pydantic import Field, JsonValue

from .common import (
    ActionResponse,
    APIRequest,
    APIResponse,
    NonEmptyStr,
    PlayerInfo,
    ServerName,
    ServerSummary,
    SuccessResponse,
)


class StartServerRequest(APIRequest):
    server_name: ServerName


class StopServerRequest(APIRequest):
    server_name: ServerName


class RestartServerRequest(APIRequest):
    server_name: ServerName
    send_message: bool = True


class StartServerResponse(APIResponse):
    server_name: ServerName
    status: Literal["success"] = "success"
    outcome: Literal["started", "already_running"]
    message: str


class StopServerResponse(APIResponse):
    server_name: ServerName
    status: Literal["success"] = "success"
    outcome: Literal["stopped", "already_stopped"]
    message: str


class RestartServerResponse(APIResponse):
    server_name: ServerName
    status: Literal["success"] = "success"
    outcome: Literal["restarted", "started"]
    message: str


class GetServerSettingRequest(APIRequest):
    server_name: ServerName
    key: NonEmptyStr


class GetServerSettingResponse(SuccessResponse):
    value: JsonValue


class SetServerSettingRequest(APIRequest):
    server_name: ServerName
    key: NonEmptyStr
    value: JsonValue


class SetServerSettingResponse(ActionResponse):
    pass


class SetServerCustomValueRequest(APIRequest):
    server_name: ServerName
    key: NonEmptyStr
    value: JsonValue


class SetServerCustomValueResponse(ActionResponse):
    pass


class GetAllServerSettingsRequest(APIRequest):
    server_name: ServerName


class GetAllServerSettingsResponse(SuccessResponse):
    settings: dict[str, JsonValue]


class GetServerSummaryRequest(APIRequest):
    server_name: ServerName


class GetServerSummaryResponse(SuccessResponse):
    summary: ServerSummary


class SendCommandRequest(APIRequest):
    server_name: ServerName
    command: NonEmptyStr


class SendCommandResponse(ActionResponse):
    pass


class DeleteServerDataRequest(APIRequest):
    server_name: ServerName
    stop_if_running: bool = True


class DeleteServerDataResponse(ActionResponse):
    pass


class SetServerStatusRequest(APIRequest):
    server_name: ServerName
    status: NonEmptyStr


class SetServerStatusResponse(SuccessResponse):
    server_name: ServerName
    previous_status: str | None = None
    new_status: str


class UpdateServerPlayerStatsRequest(APIRequest):
    server_name: ServerName
    player_count: Annotated[int, Field(ge=0)]
    players: list[PlayerInfo]


class UpdateServerPlayerStatsResponse(SuccessResponse):
    server_name: ServerName
    player_count: int = Field(ge=0)
    players: list[PlayerInfo]
