# src/bedrock_server_manager/services/plugin_service.py
"""
Service managing plugin state mutations and configuration persistence.
"""

from typing import TYPE_CHECKING, Any, Dict, Optional

from ..state.models import PluginInfoState

if TYPE_CHECKING:
    from ..context import AppContext


class PluginService:
    """Handles domain logic and mutations for application plugins."""

    def __init__(self, app_context: "AppContext"):
        self.app_context = app_context

    def get_plugin_state(self, plugin_name: str) -> Optional[PluginInfoState]:
        """Retrieves a plugin state model snapshot."""
        plugin = self.app_context.state.plugins.get(plugin_name)
        if plugin:
            res: PluginInfoState = plugin.model_copy()
            return res
        return None

    async def register_or_update_plugin(
        self,
        plugin_name: str,
        enabled: Optional[bool] = None,
        version: Optional[str] = None,
        author: Optional[str] = None,
        description: Optional[str] = None,
        settings: Optional[Dict[str, Any]] = None,
    ) -> PluginInfoState:
        """Registers or updates a plugin state record and marks dirty state."""
        existing = self.app_context.state.plugins.get(plugin_name)
        if existing:
            data = existing.model_dump()
            if enabled is not None:
                data["enabled"] = enabled
            if version is not None:
                data["version"] = version
            if author is not None:
                data["author"] = author
            if description is not None:
                data["description"] = description
            if settings is not None:
                data["settings"] = settings
            plugin = PluginInfoState(**data)
        else:
            plugin = PluginInfoState(
                plugin_name=plugin_name,
                enabled=enabled if enabled is not None else True,
                version=version,
                author=author,
                description=description,
                settings=settings or {},
            )

        self.app_context.state.plugins.set(plugin)
        return plugin

    async def set_enabled(self, plugin_name: str, enabled: bool) -> None:
        """Enables or disables a plugin state."""
        await self.register_or_update_plugin(plugin_name, enabled=enabled)
