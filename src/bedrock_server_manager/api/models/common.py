"""Serializable contracts shared by API domains; no runtime dependencies."""

from typing import Annotated, ClassVar, Literal, Self

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    model_validator,
)
from pydantic.json_schema import JsonSchemaValue

from ...contracts import DataContract, FailureInfo
from ...contracts import NonEmptyStr as NonEmptyStr
from ...contracts import ServerName as ServerName
from ...state_revision import StateRevision as StateRevision


class APIRequest(DataContract):
    """Strict input validation before side effects."""


class APIResponse(DataContract):
    """Validated transport output."""


class APIErrorResponse(FailureInfo, APIResponse):
    """Safe serialized failure; Python callers receive exceptions."""


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


class PartialResponse(APIResponse):
    status: Literal["success", "partial"] = "success"
    message: str | None = None


def action_response_schema(schema: JsonSchemaValue, model: type[BaseModel]) -> None:
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

    status: Literal["success", "skipped", "partial"] = "success"
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


class ServerSummary(StateRevision):
    players_available: bool = True
    name: str
    status: str
    version: str
    player_count: int = Field(default=0, ge=0)
    players: list[PlayerInfo] = Field(default_factory=list)

    @model_validator(mode="after")
    def coherent_player_count(self) -> Self:
        if self.player_count != len(self.players):
            raise ValueError("player_count must match the player list")
        return self


class ErrorEnvelope(APIResponse):
    error: APIErrorResponse


__all__ = [
    "APIRequest",
    "APIResponse",
    "APIErrorResponse",
    "NonEmptyStr",
    "ServerName",
    "PermissionLevel",
    "PackType",
    "BackupType",
    "SuccessResponse",
    "ActionResponse",
    "PlayerInfo",
    "StateRevision",
    "ServerSummary",
    "ErrorEnvelope",
    "PartialResponse",
]
