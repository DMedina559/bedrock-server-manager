# src/bedrock_server_manager/services/settings_service.py
"""
Service managing application setting mutations and read operations.
"""

import logging
from typing import TYPE_CHECKING, Any, Dict, Optional, cast

from ..state.changeset import ChangeSet

if TYPE_CHECKING:
    from ..config.settings import Settings
    from ..db.storage import Storage
    from ..state.app_state import AppState


logger = logging.getLogger(__name__)


async def migrate_bootstrap_cors(storage: "Storage", value: Any) -> None:
    """Import legacy CORS policy once, without replacing a database policy."""
    from ..state.settings import SettingsState

    async with storage.transaction() as session:
        existing = await storage.settings_repo.get_all_settings(session)
        web = existing.get("web", {})
        if "web.cors_origins" in existing or (
            isinstance(web, dict) and "cors_origins" in web
        ):
            return
        origins = [value] if isinstance(value, str) else value
        candidate = SettingsState.from_dict(existing, data_dir=storage.data_dir)
        candidate.set("web.cors_origins", origins)
        await storage.settings_repo.save_settings(session, candidate.to_dict())
        logger.info("Imported legacy web.cors_origins into database settings")


class SettingsService:
    """Handle business logic and persistence for application settings."""

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
        """Return a setting value via AppState."""
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
        """Return all configuration settings as a dictionary snapshot."""
        return cast(Dict[str, Any], self.state.settings.to_dict())
