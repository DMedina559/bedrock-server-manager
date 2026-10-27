"""Shared creation choices for backup APIs, settings and plugin forms.

Archive/restore components additionally include server_directory. That internal
component is selected through full mode, never through an individual checkbox.
"""

from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

BackupMode = Literal["world", "selected", "full"]
SelectableComponent = Literal[
    "world",
    "server.properties",
    "allowlist.json",
    "permissions.json",
    "script_config",
    "bsm_settings",
    "behavior_packs",
    "resource_packs",
    "development_behavior_packs",
    "development_resource_packs",
]
DEFAULT_COMPONENTS: tuple[SelectableComponent, ...] = (
    "world",
    "server.properties",
    "allowlist.json",
    "permissions.json",
    "script_config",
    "bsm_settings",
)
COMPONENT_LABELS: dict[SelectableComponent, str] = {
    "world": "Active world (includes world packs)",
    "server.properties": "Server properties",
    "allowlist.json": "Allowlist",
    "permissions.json": "Player permissions",
    "script_config": "Script configuration",
    "bsm_settings": "BSM server settings",
    "behavior_packs": "Server behavior packs",
    "resource_packs": "Server resource packs",
    "development_behavior_packs": "Development behavior packs",
    "development_resource_packs": "Development resource packs",
}


def unique_components(value: list[SelectableComponent]) -> list[SelectableComponent]:
    if len(value) != len(set(value)):
        raise ValueError("Choose backup components without duplicates")
    return value


BackupComponents = Annotated[
    list[SelectableComponent],
    Field(
        min_length=1,
        json_schema_extra={
            "uniqueItems": True,
            "x-bsm-choice-labels": COMPONENT_LABELS,
            "x-bsm-default-components": list(DEFAULT_COMPONENTS),
        },
    ),
    AfterValidator(unique_components),
]


class BackupContentSelection(BaseModel):
    """Validated creation contents; full mode expands internally during capture."""

    model_config = ConfigDict(extra="forbid", strict=True)
    mode: BackupMode = "selected"
    components: BackupComponents = Field(
        default_factory=lambda: list(DEFAULT_COMPONENTS)
    )
