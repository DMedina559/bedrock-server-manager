"""Serializable plugins API request and response contracts."""

from pydantic import JsonValue

from .common import (
    ActionResponse,
    APIRequest,
    APIResponse,
    NonEmptyStr,
    SuccessResponse,
)


class PluginInfo(APIResponse):
    enabled: bool
    description: str = ""
    version: str = "N/A"
    author: str = ""
    status: str = "UNKNOWN"


class GetPluginStatusesRequest(APIRequest):
    pass


class GetPluginStatusesResponse(SuccessResponse):
    plugins: dict[str, PluginInfo]


class SetPluginStatusRequest(APIRequest):
    target_plugin_name: NonEmptyStr
    enabled: bool


class SetPluginStatusResponse(ActionResponse):
    pass


class ReloadSinglePluginRequest(APIRequest):
    target_plugin_name: NonEmptyStr


class ReloadSinglePluginResponse(ActionResponse):
    pass


class ReloadPluginsRequest(APIRequest):
    pass


class ReloadPluginsResponse(ActionResponse):
    pass


class TriggerExternalAppEventRequest(APIRequest):
    event_name: NonEmptyStr
    payload: dict[str, JsonValue] | None = None


class TriggerExternalAppEventResponse(ActionResponse):
    pass
