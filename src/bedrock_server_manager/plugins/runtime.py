# src/bedrock_server_manager/plugins/runtime.py
"""
Runtime management objects for plugin execution (PluginRuntime vs PluginState).
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class PluginRuntime:
    """
    Ephemeral runtime tracking for loaded plugins.
    Separates running process handles and modules from persistent PluginInfoState.
    """

    plugin_name: str
    loaded: bool = False
    status: str = "UNLOADED"  # LOADED, DISABLED, ERROR, UNLOADED
    module_name: Optional[str] = None
    error_message: Optional[str] = None
    registered_events: List[str] = field(default_factory=list)
    active_tasks: List[str] = field(default_factory=list)
