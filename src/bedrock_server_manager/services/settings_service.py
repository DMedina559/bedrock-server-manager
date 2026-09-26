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
        settings: Optional["Settings"] = None,
        storage: Optional["Storage"] = None,
    ):
        self.state = state
        self.settings = settings
        self.storage = storage

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieves a setting value via AppState."""
        return self.state.settings.get(key, default)

    async def update_setting(self, key: str, value: Any) -> None:
        """Updates a setting value in AppState and registers dirty state for persistence."""
        if self.get(key) == value:
            return

        async with self.state.lock:
            self.state.settings.set(key, value)
            if self.settings is not None and hasattr(self.settings, "_settings"):
                setattr(self.settings, "_settings", self.state.settings.to_dict())

            changeset = ChangeSet()
            changeset.add_setting(key)

            if self.storage is not None and hasattr(self.storage, "apply_changeset"):
                await self.storage.apply_changeset(self.state, changeset)

    async def get_all_settings(self) -> Dict[str, Any]:
        """Returns all configuration settings as a dictionary snapshot."""
        return cast(Dict[str, Any], self.state.settings.to_dict())
