# src/bedrock_server_manager/services/settings_service.py
"""
Service managing application setting mutations and read operations.
"""

from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    from ..context import AppContext


class SettingsService:
    """Handles business logic and persistence for application settings."""

    def __init__(self, app_context: "AppContext"):
        self.app_context = app_context

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieves a setting value via AppState."""
        return self.app_context.settings.get(key, default)

    async def update_setting(self, key: str, value: Any) -> None:
        """Updates a setting value in AppState and registers dirty state for persistence."""
        if self.get(key) == value:
            return

        self.app_context.state.settings.set(key, value)
        if self.app_context._settings is not None:
            self.app_context._settings._settings = (
                self.app_context.state.settings.to_dict()
            )

    async def get_all_settings(self) -> Dict[str, Any]:
        """Returns all configuration settings as a dictionary snapshot."""
        return self.app_context.state.settings.to_dict()
