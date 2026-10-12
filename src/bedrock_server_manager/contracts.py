"""Transport-independent validated data shared by application layers."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue

NonEmptyStr = Annotated[str, Field(strict=True, min_length=1, pattern=r".*\S.*")]
ServerName = Annotated[
    str,
    Field(strict=True, min_length=1, pattern=r"^[a-zA-Z0-9_-]+$", examples=["example"]),
]


class DataContract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
        revalidate_instances="always",
        validate_default=True,
        allow_inf_nan=False,
    )


class FailureInfo(DataContract):
    code: Literal[
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error",
    ]
    message: str
    details: dict[str, JsonValue] = Field(default_factory=dict)


class ClassifiedFailure(DataContract):
    error: FailureInfo
    status_code: int = Field(ge=400, le=599)
    expected: bool
