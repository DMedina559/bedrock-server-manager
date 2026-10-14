# bedrock_server_manager/config/settings.py
"""Application settings backed by typed state and durable storage."""

import collections.abc
import logging
from typing import TYPE_CHECKING, Any, Dict, Optional, cast

if TYPE_CHECKING:
    from ..db.storage import Storage
    from ..state.app_state import AppState


logger = logging.getLogger(__name__)


def deep_merge(
    source: Dict[Any, Any] | collections.abc.Mapping, destination: Dict[Any, Any]
) -> Dict[Any, Any]:
    """Merge source values recursively into destination and return destination.

    Conflicting source values take precedence; destination is modified in place.
    """
    for key, value in source.items():
        if isinstance(value, dict):
            destination[key] = deep_merge(value, destination.get(key, {}))
        else:
            destination[key] = value
    return destination


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


class Settings:
    """Read and persist application settings through typed state.

    Use dotted keys with :meth:`get` and :meth:`set`.
    """

    def __init__(
        self,
        config_dir: str,
        data_dir: str,
        app_context: Optional[Any] = None,
    ):
        """Initialize the Settings object."""
        logger.debug("Initializing Settings")
        self.data_dir = data_dir
        self.config_dir = config_dir
        self.app_context = app_context

    @property
    def _settings(self) -> Dict[str, Any]:
        """Compatibility snapshot derived from live state, never a second cache."""
        return self.state.settings.to_dict() if self.app_context is not None else {}

    @property
    def state(self) -> "AppState":
        if self.app_context is None:
            from ..error import BSMError

            raise BSMError("Settings.state accessed without an associated app_context.")
        from ..state.app_state import AppState

        return cast(AppState, self.app_context.state)

    @property
    def storage(self) -> "Storage":
        if self.app_context is None:
            from ..error import BSMError

            raise BSMError(
                "Settings.storage accessed without an associated app_context."
            )
        from ..db.storage import Storage

        return cast(Storage, self.app_context.storage)

    @property
    def default_config(self) -> dict:
        """Return default settings with paths rooted in the application data directory."""

        from ..state.settings import SettingsState

        return SettingsState.create_defaults(self.data_dir).to_dict()

    def get(self, key: str, default: Any = None) -> Any:
        """Return a setting value using dot-notation for nested access."""
        val = self.state.settings.get(key, default)
        return val if val is not None else default

    async def load(self) -> None:
        """Load settings from the database asynchronously."""
        await self.storage.load_state(self.state)

    async def set(self, key: str, value: Any) -> None:
        """Set a configuration value using dot-notation asynchronously via
        SettingsService.
        """
        if self.app_context is None:
            from ..error import BSMError

            raise BSMError("Settings.set accessed without an associated app_context.")
        await self.app_context.settings_service.update_setting(key, value)

    async def reload(self):
        """Reloads the settings from the database asynchronously."""
        logger.debug("Reloading configuration from database")
        await self.load()
        logger.info("Configuration reloaded successfully.")
