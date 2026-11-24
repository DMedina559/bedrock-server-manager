"""Serializable application API and HTTP contracts."""

from pydantic import Field

from .common import (
    APIRequest,
    PartialResponse,
    ResourceFailure,
    ServerSummary,
    StateRevision,
    SuccessResponse,
)


class ListAvailableWorldsRequest(APIRequest):
    pass


class ListAvailableWorldsResponse(SuccessResponse):
    files: list[str]


class GetAllServersDataRequest(APIRequest):
    pass


class GetAllServersDataResponse(PartialResponse, StateRevision):
    errors: list[ResourceFailure] = Field(default_factory=list)
    servers: list[ServerSummary]


class GetSystemAndAppInfoRequest(APIRequest):
    pass


class GetSystemAndAppInfoResponse(SuccessResponse):
    os_type: str
    app_version: str
    splash_text: str
    timezone: str = "UTC"


class UpdateServerStatusesRequest(APIRequest):
    pass


class UpdateServerStatusesResponse(PartialResponse):
    updated_servers_count: int = Field(default=0, ge=0)
    errors: list[ResourceFailure] = Field(default_factory=list)
