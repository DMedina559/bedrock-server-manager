# src/bedrock_server_manager/services/settings_service.py
"""
Service managing application setting mutations and read operations.
"""

from typing import TYPE_CHECKING, Any, Dict, Optional, cast

from ..state.changeset import ChangeSet

if TYPE_CHECKING:
    from ..context import AppContext


class SettingsService:
    """Handles business logic and persistence for application settings."""

    def __init__(
        self,
        app_context: Optional["AppContext"] = None,
        state: Optional[Any] = None,
        settings: Optional[Any] = None,
        storage: Optional[Any] = None,
    ):
        self._app_context = app_context
        self._state = state
        self._settings = settings
        self._storage = storage

    @property
    def app_context(self) -> Optional["AppContext"]:
        return self._app_context

    @property
    def state(self) -> Any:
        if self._state is not None:
            return self._state
        if self._app_context is not None:
            return self._app_context.state
        raise ValueError(
            "SettingsService has no AppState provided or set via AppContext."
        )

    @property
    def settings(self) -> Any:
        if self._settings is not None:
            return self._settings
        if self._app_context is not None:
            return self._app_context.settings
        raise ValueError(
            "SettingsService has no Settings provided or set via AppContext."
        )

    @property
    def storage(self) -> Optional[Any]:
        if self._storage is not None:
            return self._storage
        if (
            self._app_context is not None
            and getattr(self._app_context, "_storage", None) is not None
        ):
            return self._app_context.storage
        return None

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieves a setting value via AppState."""
        return self.state.settings.get(key, default)

    async def update_setting(self, key: str, value: Any) -> None:
        """Updates a setting value in AppState and registers dirty state for persistence."""
        if self.get(key) == value:
            return

        self.state.settings.set(key, value)
        if self._settings is not None and hasattr(self._settings, "_settings"):
            setattr(self._settings, "_settings", self.state.settings.to_dict())
        elif (
            self._app_context is not None
            and getattr(self._app_context, "_settings", None) is not None
        ):
            setattr(
                self._app_context._settings,
                "_settings",
                self.state.settings.to_dict(),
            )

        changeset = ChangeSet()
        changeset.add_setting(key)

        if self.storage is not None and hasattr(self.storage, "apply_changeset"):
            await self.storage.apply_changeset(self.state, changeset)

    async def get_all_settings(self) -> Dict[str, Any]:
        """Returns all configuration settings as a dictionary snapshot."""
        return cast(Dict[str, Any], self.state.settings.to_dict())
