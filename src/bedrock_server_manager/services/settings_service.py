# src/bedrock_server_manager/services/settings_service.py
"""
Service managing application setting mutations and read operations.
"""

from typing import TYPE_CHECKING, Any, Dict, Optional, cast

from ..state.changeset import ChangeSet

if TYPE_CHECKING:
    from ..config.settings import Settings
    from ..db.storage import Storage
    from ..state.app_state import AppState


class SettingsService:
    """Handles business logic and persistence for application settings."""

    def __init__(
        self,
        state: "AppState",
        storage: "Storage",
        settings: Optional["Settings"] = None,
        plugin_service=None,
    ):
        self.state = state
        self.storage = storage
        self.settings = settings
        self.plugin_service = plugin_service

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieves a setting value via AppState."""
        return self.state.settings.get(key, default)

    async def update_setting(self, key: str, value: Any) -> None:
        """Updates a setting value in AppState and registers dirty state for persistence."""

        def mutate(candidate):
            local_key, local_value = key, value
            if (
                key == "plugin_settings" or key.startswith("plugin_settings.")
            ) and self.plugin_service is not None:
                candidate.set(local_key, local_value)
                checked = {
                    name: self.plugin_service.validate_settings(name, values)
                    for name, values in candidate.plugin_settings.items()
                }
                local_key, local_value = "plugin_settings", checked
            if not candidate.set(local_key, local_value):
                return

        changeset = ChangeSet()
        changeset.add_setting(key)

        await self.storage.commit_settings(self.state, changeset, mutate)

    async def get_all_settings(self) -> Dict[str, Any]:
        """Returns all configuration settings as a dictionary snapshot."""
        return cast(Dict[str, Any], self.state.settings.to_dict())
