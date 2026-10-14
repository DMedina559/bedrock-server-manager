"""Serializable websocket API request and response contracts."""

from typing import Literal

from pydantic import Field, JsonValue

from ...results import DeliveryResult
from .common import ActionResponse, APIRequest, NonEmptyStr


class BroadcastRequest(APIRequest):
    topic: NonEmptyStr
    data: JsonValue


class BroadcastResponse(ActionResponse):
    delivery: DeliveryResult = Field(default_factory=DeliveryResult)


class SendToUserRequest(APIRequest):
    username: NonEmptyStr
    data: JsonValue


class SendToUserResponse(ActionResponse):
    delivery: DeliveryResult = Field(default_factory=DeliveryResult)


class SendToClientRequest(APIRequest):
    client_id: NonEmptyStr
    data: JsonValue


class SendToClientResponse(ActionResponse):
    delivery: DeliveryResult = Field(default_factory=DeliveryResult)


class UnregisterDataProviderRequest(APIRequest):
    topic: NonEmptyStr


class UnregisterDataProviderResponse(ActionResponse):
    outcome: Literal["removed", "already_absent"]


class PublishWsEventRequest(APIRequest):
    event_name: NonEmptyStr
    data: JsonValue


class PublishWsEventResponse(ActionResponse):
    delivery: DeliveryResult = Field(default_factory=DeliveryResult)
