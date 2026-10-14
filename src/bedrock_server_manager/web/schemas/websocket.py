"""Validated WebSocket frames and serializable provider data."""

from typing import Literal

from pydantic import BaseModel, JsonValue, ValidationError

from ...api.models.common import APIErrorResponse, APIRequest, APIResponse, NonEmptyStr
from ...plugins.api_contract import APIResponseValidationError


class AuthenticationFrame(APIRequest):
    action: Literal["authenticate"]
    token: str | None = None


class ClientFrame(APIRequest):
    action: Literal["subscribe", "unsubscribe", "request", "request_data"]
    topic: NonEmptyStr
    data: JsonValue = None
    request_id: str | int | None = None


class SocketReply(APIResponse):
    status: Literal["success", "error"]
    type: Literal["response"] | None = None
    topic: str | None = None
    request_id: str | int | None = None
    message: str | None = None
    data: JsonValue = None
    error: APIErrorResponse | None = None


class JSONPayload(APIResponse):
    value: JsonValue


def json_payload(data: object) -> JSONPayload:
    try:
        if isinstance(data, BaseModel):
            data = data.model_dump(mode="json")
        return JSONPayload.model_validate({"value": data})
    except (ValidationError, ValueError, TypeError) as error:
        raise APIResponseValidationError(
            "WebSocket provider returned invalid JSON data."
        ) from error
