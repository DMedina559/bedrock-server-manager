"""Serializable application API request and response contracts."""

from pydantic import Field

from .common import APIRequest, ServerSummary, SuccessResponse


class ListAvailableWorldsRequest(APIRequest):
    pass


class ListAvailableWorldsResponse(SuccessResponse):
    files: list[str]


class GetAllServersDataRequest(APIRequest):
    pass


class GetAllServersDataResponse(SuccessResponse):
    servers: list[ServerSummary]


class GetSystemAndAppInfoRequest(APIRequest):
    pass


class GetSystemAndAppInfoResponse(SuccessResponse):
    os_type: str
    app_version: str
    splash_text: str


class UpdateServerStatusesRequest(APIRequest):
    pass


class UpdateServerStatusesResponse(SuccessResponse):
    updated_servers_count: int = Field(default=0, ge=0)
    errors: list[str] = Field(default_factory=list)
