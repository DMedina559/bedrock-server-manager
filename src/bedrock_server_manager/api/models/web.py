"""Serializable web API request and response contracts."""

from typing import Annotated, Literal

from pydantic import Field, SecretStr

from .common import ActionResponse, APIRequest, APIResponse, SuccessResponse


class StartWebServerRequest(APIRequest):
    host: str | None = None
    port: Annotated[int, Field(ge=1, le=65535)] | None = None
    debug: bool = False
    mode: Literal["direct", "detached"] = "direct"


class StartWebServerResponse(ActionResponse):
    pid: int | None = None


class StopWebServerRequest(APIRequest):
    pass


class StopWebServerResponse(ActionResponse):
    pass


class GetWebServerStatusRequest(APIRequest):
    pass


class GetWebServerStatusResponse(APIResponse):
    status: Literal["STOPPED", "RUNNING", "MISMATCHED_PROCESS"]
    pid: int | None = None
    message: str


class CreateWebUiServiceRequest(APIRequest):
    autostart: bool = False
    system: bool = False
    username: str | None = None
    password: SecretStr | None = Field(default=None, exclude=True, repr=False)


class CreateWebUiServiceResponse(ActionResponse):
    pass


class EnableWebUiServiceRequest(APIRequest):
    system: bool = False


class EnableWebUiServiceResponse(ActionResponse):
    pass


class DisableWebUiServiceRequest(APIRequest):
    system: bool = False


class DisableWebUiServiceResponse(ActionResponse):
    pass


class RemoveWebUiServiceRequest(APIRequest):
    system: bool = False


class RemoveWebUiServiceResponse(ActionResponse):
    pass


class GetWebUiServiceStatusRequest(APIRequest):
    system: bool = False


class GetWebUiServiceStatusResponse(SuccessResponse):
    service_exists: bool
    is_active: bool
    is_enabled: bool
