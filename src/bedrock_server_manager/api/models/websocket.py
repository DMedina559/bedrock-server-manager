"""Serializable websocket API request and response contracts."""

from pydantic import JsonValue

from .common import ActionResponse, APIRequest, NonEmptyStr


class BroadcastRequest(APIRequest):
    topic: NonEmptyStr
    data: JsonValue


class BroadcastResponse(ActionResponse):
    pass


class SendToUserRequest(APIRequest):
    username: NonEmptyStr
    data: JsonValue


class SendToUserResponse(ActionResponse):
    pass


class SendToClientRequest(APIRequest):
    client_id: NonEmptyStr
    data: JsonValue


class SendToClientResponse(ActionResponse):
    pass


class UnregisterDataProviderRequest(APIRequest):
    topic: NonEmptyStr


class UnregisterDataProviderResponse(ActionResponse):
    pass


class PublishWsEventRequest(APIRequest):
    event_name: NonEmptyStr
    data: JsonValue


class PublishWsEventResponse(ActionResponse):
    pass
