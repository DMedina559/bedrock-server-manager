"""Data boundaries shared by core consumers; no API/runtime dependencies."""

from typing import Annotated, Literal

from pydantic import ConfigDict, Field, JsonValue, TypeAdapter, field_validator

from ..state.models import PersistentRecord

NonEmptyText = Annotated[str, Field(min_length=1)]
VersionPart = Annotated[int, Field(ge=0)]


class PlayerRecord(PersistentRecord):
    name: str
    xuid: str


class SummaryRecord(PersistentRecord):
    name: str
    status: str
    version: str
    player_count: int = Field(ge=0)
    players: list[PlayerRecord]


class ProcessRecord(PersistentRecord):
    pid: int = Field(gt=0)
    cpu_percent: float = Field(ge=0)
    memory_mb: float = Field(ge=0)
    uptime: str


class ExternalRecord(PersistentRecord):
    """Preserve Minecraft extensions while validating known fields and JSON."""

    model_config = ConfigDict(extra="allow")
    __pydantic_extra__: dict[str, JsonValue] = Field(init=False)


class AllowlistEntry(ExternalRecord):
    name: NonEmptyText
    xuid: str | None = None
    ignoresPlayerLimit: bool = False


class PermissionEntry(ExternalRecord):
    xuid: NonEmptyText
    permission: Literal["visitor", "member", "operator"]
    name: str | None = None

    @field_validator("permission", mode="before")
    @classmethod
    def normalize_permission(cls, value: object) -> object:
        return value.lower() if isinstance(value, str) else value


class ManifestHeader(ExternalRecord):
    uuid: NonEmptyText
    version: Annotated[list[VersionPart], Field(min_length=3, max_length=3)]
    name: NonEmptyText


class ManifestModule(ExternalRecord):
    type: str | None = None
    description: str | None = None


class SubpackRecord(ExternalRecord):
    folder_name: NonEmptyText
    name: str | None = None
    memory_tier: int | None = Field(default=None, ge=0)


class ManifestRecord(ExternalRecord):
    header: ManifestHeader
    modules: Annotated[list[ManifestModule], Field(min_length=1)]
    subpacks: list[SubpackRecord] = Field(default_factory=list)


ALLOWLIST = TypeAdapter(list[AllowlistEntry])
PERMISSIONS = TypeAdapter(list[PermissionEntry])
