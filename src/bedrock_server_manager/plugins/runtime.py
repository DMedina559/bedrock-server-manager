# src/bedrock_server_manager/plugins/runtime.py
"""
Runtime management objects for plugin execution (PluginRuntime vs PluginState).
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class PluginRuntime(BaseModel):
    """
    Ephemeral runtime tracking for loaded plugins.
    Separates running process handles and modules from persistent PluginInfoState.
    """

    plugin_name: str
    loaded: bool = False
    status: str = "UNLOADED"  # LOADED, DISABLED, ERROR, UNLOADED
    module_name: Optional[str] = None
    error_message: Optional[str] = None
    registered_events: List[str] = Field(default_factory=list)
    active_tasks: List[str] = Field(default_factory=list)

    model_config = {"arbitrary_types_allowed": True}
