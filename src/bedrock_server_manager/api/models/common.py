"""Serializable contracts shared by API domains; no runtime dependencies."""

from typing import Annotated, ClassVar, Literal, Self

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    JsonValue,
    model_validator,
)
from pydantic.json_schema import JsonSchemaValue


class APIRequest(BaseModel):
    """Reject misspelled fields and revalidate even constructed model instances."""

    model_config = ConfigDict(
        extra="forbid", strict=True, revalidate_instances="always"
    )


class APIResponse(BaseModel):
    """Validated output data. Nested containers are not deeply immutable."""

    model_config = ConfigDict(
        extra="forbid", strict=True, frozen=True, revalidate_instances="always"
    )


class APIErrorResponse(APIResponse):
    """Safe transport representation; Python API callers receive exceptions."""

    code: Literal[
        "validation_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
    ]
    message: str
    details: dict[str, JsonValue] = Field(default_factory=dict)


NonEmptyStr = Annotated[str, Field(strict=True, min_length=1, pattern=r".*\S.*")]
ServerName = Annotated[
    str,
    Field(strict=True, min_length=1, pattern=r"^[a-zA-Z0-9_-]+$", examples=["example"]),
]
PermissionLevel = Annotated[
    Literal["visitor", "member", "operator"],
    BeforeValidator(lambda value: value.lower() if isinstance(value, str) else value),
]
PackType = Annotated[
    Literal["behavior", "resource"],
    BeforeValidator(lambda value: value.lower() if isinstance(value, str) else value),
]
BackupType = Annotated[
    Literal["world", "properties", "allowlist", "permissions", "all"],
    BeforeValidator(lambda value: value.lower() if isinstance(value, str) else value),
]


class SuccessResponse(APIResponse):
    status: Literal["success"] = "success"
    message: str | None = None


def action_response_schema(schema: JsonSchemaValue, model: type) -> None:
    """Describe successful data requirements that do not apply to skipped work."""
    fields = getattr(model, "required_on_success", ())
    if fields:
        schema["allOf"] = [
            {
                "if": {"properties": {"status": {"const": "success"}}},
                "then": {
                    "required": list(fields),
                    "properties": {
                        field: {"not": {"type": "null"}} for field in fields
                    },
                },
            }
        ]


class ActionResponse(APIResponse):
    model_config = ConfigDict(json_schema_extra=action_response_schema)

    status: Literal["success", "skipped"] = "success"
    message: str
    required_on_success: ClassVar[tuple[str, ...]] = ()

    @model_validator(mode="after")
    def check_success_data(self) -> Self:
        if self.status == "success":
            for field in self.required_on_success:
                if getattr(self, field) is None:
                    raise ValueError(f"Successful response requires {field}")
        return self


class PlayerInfo(APIResponse):
    name: str
    xuid: str


class ServerSummary(APIResponse):
    name: str
    status: str
    version: str
    player_count: int = Field(default=0, ge=0)
    players: list[PlayerInfo] = Field(default_factory=list)
