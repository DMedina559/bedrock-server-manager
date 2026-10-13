"""Serializable web API request and response contracts."""

from pydantic import Field, SecretStr

from .common import ActionResponse, APIRequest, SuccessResponse


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
