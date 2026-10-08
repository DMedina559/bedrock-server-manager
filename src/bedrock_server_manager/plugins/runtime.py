"""Validated plugin runtime snapshots; execution handles stay in PluginManager."""

from typing import Literal
from pydantic import ConfigDict, Field
from ..state.models import PersistentRecord

PluginStatus = Literal["LOADED", "DISABLED", "ERROR", "UNLOADED", "UNKNOWN"]

class PluginRuntime(PersistentRecord):
    model_config = ConfigDict(frozen=True)
    plugin_name: str
    status: PluginStatus = "UNLOADED"
    module_name: str | None = None
    error_message: str | None = None
    registered_events: list[str] = Field(default_factory=list)
    active_tasks: list[str] = Field(default_factory=list)

    @property
    def loaded(self) -> bool:
        return self.status == "LOADED"
