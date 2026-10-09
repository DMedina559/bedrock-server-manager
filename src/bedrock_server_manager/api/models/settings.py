"""Serializable settings API request and response contracts."""

from pydantic import JsonValue

from .common import ActionResponse, APIRequest, NonEmptyStr, SuccessResponse


class GetGlobalSettingRequest(APIRequest):
    key: NonEmptyStr


class GetGlobalSettingResponse(SuccessResponse):
    value: JsonValue


class GetAllGlobalSettingsRequest(APIRequest):
    pass


class GetAllGlobalSettingsResponse(SuccessResponse):
    settings: dict[str, JsonValue]


class SetGlobalSettingRequest(APIRequest):
    key: NonEmptyStr
    value: JsonValue


class SetGlobalSettingResponse(ActionResponse):
    pass


class SetCustomGlobalSettingRequest(APIRequest):
    key: NonEmptyStr
    value: JsonValue


class SetCustomGlobalSettingResponse(ActionResponse):
    pass


class ReloadGlobalSettingsRequest(APIRequest):
    pass


class ReloadGlobalSettingsResponse(ActionResponse):
    pass
