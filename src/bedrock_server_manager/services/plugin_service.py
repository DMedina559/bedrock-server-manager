# src/bedrock_server_manager/services/plugin_service.py
"""
Service managing plugin state mutations and configuration persistence.
"""

from typing import TYPE_CHECKING, Dict, Optional

from pydantic import JsonValue

from ..state.changeset import ChangeSet
from ..state.models import PluginInfoState
from ..state.updates import UNSET, PluginUpdate, Unset

if TYPE_CHECKING:
    from ..db.storage import Storage
    from ..state.app_state import AppState


class PluginService:
    """Handles domain logic and mutations for application plugins."""

    def __init__(
        self,
        state: "AppState",
        storage: "Storage",
    ):
        self.state = state
        self.storage = storage

    def get_plugin_state(self, plugin_name: str) -> Optional[PluginInfoState]:
        """Retrieves a plugin state model snapshot."""
        plugin = self.state.plugins.get(plugin_name)
        if plugin:
            res: PluginInfoState = plugin.model_copy()
            return res
        return None

    async def register_or_update_plugin(
        self,
        plugin_name: str,
        enabled: Optional[bool] = None,
        version: str | None | Unset = UNSET,
        author: str | None | Unset = UNSET,
        description: str | None | Unset = UNSET,
        settings: Optional[Dict[str, JsonValue]] = None,
    ) -> PluginInfoState:
        """Registers or updates a plugin state record and marks dirty state."""
        async with self.state.plugins.get_lock(plugin_name):
            existing = self.state.plugins.get(plugin_name)
            values: dict[str, object] = {"plugin_name": plugin_name}
            if enabled is not None:
                values["enabled"] = enabled
            elif existing is None:
                values["enabled"] = True
            for name, value in (
                ("version", version),
                ("author", author),
                ("description", description),
            ):
                if value is not UNSET:
                    values[name] = value
            update = PluginUpdate.model_validate(values)
            data = existing.model_dump() if existing else {}
            data.update(update.model_dump(exclude_unset=True))
            plugin = PluginInfoState.model_validate(data)

            self.state.plugins.set(plugin)

        changeset = ChangeSet()
        changeset.add_plugin(plugin_name)
        if settings is not None:
            async with self.state.settings.get_lock("global"):
                values = self.state.settings.get("plugin_settings", {})
                values[plugin_name] = settings
                self.state.settings.set("plugin_settings", values)
            changeset.add_setting("plugin_settings")

        await self.storage.apply_changeset(self.state, changeset)

        return plugin

    async def set_enabled(self, plugin_name: str, enabled: bool) -> None:
        """Enables or disables a plugin state."""
        await self.register_or_update_plugin(plugin_name, enabled=enabled)

    def get_setting(self, plugin_name: str, key: str):
        """Read only the calling plugin's persisted JSON settings."""
        value = self.state.settings.get("plugin_settings", {}).get(plugin_name, {})
        for part in key.split("."):
            if not isinstance(value, dict):
                return None
            value = value.get(part)
        return value

    async def set_setting(self, plugin_name: str, key: str, value: JsonValue) -> None:
        from ..error import UserInputError

        parts = key.split(".")
        if any(not part or part.startswith("_") or "__" in part for part in parts):
            raise UserInputError("Invalid plugin setting key.")
        async with self.state.settings.get_lock("global"):
            values = self.state.settings.get("plugin_settings", {})
            current = values.setdefault(plugin_name, {})
            for part in parts[:-1]:
                child = current.setdefault(part, {})
                if not isinstance(child, dict):
                    raise UserInputError("Plugin setting path conflicts with a value.")
                current = child
            current[parts[-1]] = value
            self.state.settings.set("plugin_settings", values)
        changeset = ChangeSet()
        changeset.add_setting("plugin_settings")
        await self.storage.apply_changeset(self.state, changeset)
