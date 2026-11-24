"""Serializable settings API request and response contracts."""

from pydantic import Field, JsonValue

from .common import ActionResponse, APIRequest, NonEmptyStr, SuccessResponse


class SettingItemPayload(APIRequest):
    """Request model for a single setting key-value pair."""

    key: NonEmptyStr = Field(
        ..., description="The dot-notation key of the setting (e.g., 'web.port')."
    )
    value: JsonValue = Field(..., description="The new value for the setting.")


class GetGlobalSettingRequest(APIRequest):
    key: NonEmptyStr


class GetGlobalSettingResponse(SuccessResponse):
    value: JsonValue


class GetAllGlobalSettingsRequest(APIRequest):
    pass


class GetAllGlobalSettingsResponse(SuccessResponse):
    settings: dict[str, JsonValue]


class SetGlobalSettingRequest(SettingItemPayload):
    pass


class SetGlobalSettingResponse(ActionResponse):
    pass


class SetCustomGlobalSettingRequest(SettingItemPayload):
    pass


class SetCustomGlobalSettingResponse(ActionResponse):
    pass


class ReloadGlobalSettingsRequest(APIRequest):
    pass


class ReloadGlobalSettingsResponse(ActionResponse):
    pass
