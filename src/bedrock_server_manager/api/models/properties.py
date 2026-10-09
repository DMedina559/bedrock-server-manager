"""Serializable properties API request and response contracts."""

from .common import ActionResponse, APIRequest, NonEmptyStr, ServerName, SuccessResponse


class GetPropertiesRequest(APIRequest):
    server_name: ServerName


class GetPropertiesResponse(SuccessResponse):
    properties: dict[str, str]
    raw_content: str


class ValidatePropertyValueRequest(APIRequest):
    property_name: NonEmptyStr
    value: str


class ValidatePropertyValueResponse(SuccessResponse):
    valid: bool


class SetPropertiesRequest(APIRequest):
    server_name: ServerName
    properties_to_update: dict[str, str]
    restart_after_modify: bool = False


class SetPropertiesResponse(ActionResponse):
    pass
