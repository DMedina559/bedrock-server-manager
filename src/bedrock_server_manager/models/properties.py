"""Serializable properties API and HTTP contracts."""

from pydantic import Field

from .common import ActionResponse, APIRequest, NonEmptyStr, ServerName, SuccessResponse


class PropertiesPayload(APIRequest):
    """Request model for updating server.properties."""

    properties: dict[str, str] = Field(
        ..., description="Dictionary of properties to set."
    )


class GetPropertiesRequest(APIRequest):
    server_name: ServerName


class GetPropertiesResponse(SuccessResponse):
    properties: dict[str, str]
    raw_content: str


class GetRawPropertiesRequest(APIRequest):
    server_name: ServerName


class GetRawPropertiesResponse(SuccessResponse):
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
    server_name: ServerName
