"""Project public JSON data without passing runtime objects to observers."""

from typing import Any

from pydantic import BaseModel, JsonValue, TypeAdapter

_json_payload: TypeAdapter[JsonValue] = TypeAdapter(JsonValue)
PRIVATE_FIELDS = {
    "app_context",
    "current_user",
    "event",
    "_triggering_plugin",
    "cancellation_event",
}


def sanitize(data: Any) -> JsonValue:
    if isinstance(data, BaseModel):
        data = data.model_dump(mode="json")
    elif isinstance(data, dict):
        data = {key: sanitize(value) for key, value in data.items()}
    elif isinstance(data, (list, tuple)):
        data = [sanitize(value) for value in data]
    return _json_payload.validate_python(data, strict=True)
