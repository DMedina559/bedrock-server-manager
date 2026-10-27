"""Serializable plugins API request and response contracts."""

from typing import Literal, Self

from pydantic import Field, JsonValue, model_validator

from ...events.models import ListenerFailure
from .common import (
    ActionResponse,
    APIRequest,
    APIResponse,
    NonEmptyStr,
    ServerName,
    SuccessResponse,
)


class PluginInfo(APIResponse):
    has_settings: bool = False
    has_global_settings: bool = False
    has_server_settings: bool = False
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


class EventDispatchSummary(APIResponse):
    event_id: str
    listeners_called: int
    failures: list[ListenerFailure]


class TriggerExternalAppEventResponse(ActionResponse):
    details: EventDispatchSummary


class PluginSettingsScope(APIRequest):
    scope: Literal["plugin", "global", "server"] = Field(default="plugin", exclude=True)
    server_name: ServerName | None = Field(default=None, exclude=True)

    @model_validator(mode="after")
    def check_scope(self) -> Self:
        if (self.scope == "server") != (self.server_name is not None):
            raise ValueError(
                "Server scope requires server_name; other scopes must omit it"
            )
        return self


class GetPluginSettingRequest(PluginSettingsScope):
    key: NonEmptyStr | None = None


class GetPluginSettingResponse(SuccessResponse):
    value: JsonValue


class SetPluginSettingRequest(PluginSettingsScope):
    key: NonEmptyStr | None = None
    value: JsonValue


class SetPluginSettingResponse(ActionResponse):
    pass


class GetPluginSettingsRequest(PluginSettingsScope):
    target_plugin_name: NonEmptyStr


class GetPluginSettingsResponse(SuccessResponse):
    settings: dict[str, JsonValue]
    settings_schema: dict[str, JsonValue] | None = None


class UpdatePluginSettingsRequest(PluginSettingsScope):
    target_plugin_name: NonEmptyStr
    settings: dict[str, JsonValue]


class PluginSettingsPayload(PluginSettingsScope):
    settings: dict[str, JsonValue]
