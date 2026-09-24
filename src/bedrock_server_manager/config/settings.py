# bedrock_server_manager/config/settings.py
"""Manages application-wide configuration settings.

This module provides the `Settings` class, which is responsible for loading
settings from a database, providing default values for missing keys, saving
changes back to the database, and determining the appropriate application data and
configuration directories based on the environment.

The configuration is stored in a key-value format in the database. Settings are accessed
programmatically using dot-notation (e.g., :meth:`Settings.get('paths.servers')`).

Key components:

    - :class:`Settings`: The main class for managing configuration.
    - `settings`: A global instance of the :class:`Settings` class.

"""

import collections.abc
import logging
import os
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from ..db.database import Database

from ..db.models import Setting
from ..error import ConfigurationError

logger = logging.getLogger(__name__)


def deep_merge(
    source: Dict[Any, Any] | collections.abc.Mapping, destination: Dict[Any, Any]
) -> Dict[Any, Any]:
    """Recursively merges the ``source`` dictionary into the ``destination`` dictionary.

    This function iterates through the ``source`` dictionary. If a value is itself
    a dictionary (mapping), it recursively calls ``deep_merge`` for that nested
    dictionary. Otherwise, the value from ``source`` directly overwrites the
    corresponding value in ``destination``. The ``destination`` dictionary is
    modified in place.

    Example:

        >>> s = {'a': 1, 'b': {'c': 2, 'd': 3}}
        >>> d = {'b': {'c': 5, 'e': 6}, 'f': 7}
        >>> deep_merge(s, d)
        {'b': {'c': 2, 'd': 3, 'e': 6}, 'f': 7, 'a': 1}
        >>> d # d is modified in place
        {'b': {'c': 2, 'd': 3, 'e': 6}, 'f': 7, 'a': 1}

    Args:
        source (Dict[Any, Any]): The dictionary providing new or updated values.
            Its values will take precedence in case of conflicts.
        destination (Dict[Any, Any]): The dictionary to be updated. This dictionary
            is modified in place.

    Returns:
        Dict[Any, Any]: The merged dictionary (which is the modified ``destination``
        dictionary).
    """
    for key, value in source.items():
        if isinstance(value, dict):
            destination[key] = deep_merge(value, destination.get(key, {}))
        else:
            destination[key] = value
    return destination


class Settings:
    """Manages loading, accessing, and saving application settings.

    This class acts as a single source of truth for all configuration data.
    It handles:

        - Determining appropriate application data and configuration directories
          based on the environment (respecting ``BSM_DATA_DIR``).
        - Loading settings from a database.
        - Providing sensible default values for missing settings.

        - Saving changes back to the database.
        - Ensuring critical directories (e.g., for servers, backups, logs) exist.

    Settings are stored in a key-value format in the database and can be accessed
    programmatically using dot-notation via the :meth:`get` and :meth:`set` methods
    (e.g., ``settings.get('paths.servers')``).

    A global instance of this class, named `settings`, is typically used throughout
    the application.

    Attributes:
    """

    def __init__(
        self,
        db: "Database",
        config_dir: str,
        data_dir: str,
        app_context: Optional[Any] = None,
    ):
        """Initializes the Settings object."""
        logger.debug("Initializing Settings")
        self.db = db
        self.data_dir = data_dir
        self.config_dir = config_dir
        self.app_context = app_context
        self._settings: Dict[str, Any] = {}

    @property
    def default_config(self) -> dict:
        """Provides the default configuration values for the application.

        These defaults are used when a configuration file is not found or when a
        specific setting is missing from an existing configuration file. Paths
        are constructed dynamically based on the determined application data
        directory (see :meth:`_determine_app_data_dir`).

        The structure of the default configuration is as follows:

        .. code-block:: text

            {
                "paths": {
                    "servers": "<app_data_dir>/servers",
                    "content": "<app_data_dir>/content",
                    "downloads": "<app_data_dir>/.downloads",
                    "backups": "<app_data_dir>/backups",
                    "plugins": "<app_data_dir>/plugins",
                },
                "retention": {
                    "backups": 3,
                    "downloads": 3,
                },
                "web": {
                    "host": "127.0.0.1",
                    "jwt_secret_key": "randomly_generated_key",
                    "port": 11325,
                    "token_expires_weeks": 4,
                },
                "monitoring": {
                    "max_retiries": 3,
                    "process_interval_sec": 10,
                    "player_interval_sec": 10,
                },
                "custom": {}
            }

        Returns:
            dict: A dictionary of default settings with a nested structure.
        """

        return {
            "paths": {
                "servers": os.path.join(self.data_dir, "servers"),
                "content": os.path.join(self.data_dir, "content"),
                "downloads": os.path.join(self.data_dir, ".downloads"),
                "backups": os.path.join(self.data_dir, "backups"),
                "plugins": os.path.join(self.data_dir, "plugins"),
                "themes": os.path.join(self.data_dir, "themes"),
            },
            "retention": {
                "backups": 3,
                "downloads": 3,
            },
            "monitoring": {
                "max_retiries": 3,
                "process_interval_sec": 10,
                "player_interval_sec": 10,
            },
            "web": {
                "host": "127.0.0.1",
                "port": 11325,
                "token_expires_weeks": 4,
            },
            "custom": {},
        }

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieves a setting value using dot-notation for nested access."""
        if (
            self.app_context
            and hasattr(self.app_context, "_state")
            and self.app_context._state is not None
        ):
            val = self.app_context.state.settings.get(key, default)
            if val is not None:
                return val

        d: Any = self._settings
        try:
            for k in key.split("."):
                if isinstance(d, dict):
                    d = d[k]
                else:
                    return default
            return d
        except (KeyError, TypeError):
            return default

    async def load(self) -> None:
        """Loads settings from the database asynchronously."""
        if (
            self.app_context
            and hasattr(self.app_context, "_storage")
            and self.app_context._storage is not None
        ):
            await self.app_context.storage.load_state(self.app_context.state)
            self._settings = self.app_context.state.settings.to_dict()
            return

        from sqlalchemy.future import select

        self._settings = self.default_config

        assert self.db is not None
        async with self.db.session_manager() as db:
            result = await db.execute(select(Setting))
            settings_all = result.scalars().all()

            if not settings_all:
                logger.info(
                    "No settings found in the database. Creating with default settings asynchronously."
                )
                await self._write_config(db)
            else:
                try:
                    user_config = {}
                    for setting in settings_all:
                        user_config[setting.key] = setting.value

                    deep_merge(user_config, self._settings)

                except (ValueError, OSError) as e:
                    logger.warning(
                        f"Could not load config from database asynchronously: {e}. "
                        "Using default settings."
                    )

    async def _write_config(self, db: Any) -> None:
        """Writes the current settings dictionary to the database asynchronously."""
        from sqlalchemy.future import select

        try:
            for key, value in self._settings.items():
                result = await db.execute(select(Setting).filter_by(key=key))
                setting = result.scalars().first()
                if setting:
                    setting.value = value
                else:
                    setting = Setting(key=key, value=value)
                    db.add(setting)
            await db.commit()
        except Exception as e:
            await db.rollback()
            raise ConfigurationError(
                f"Failed to write configuration asynchronously: {e}"
            ) from e

    async def set(self, key: str, value: Any) -> None:
        """Sets a configuration value using dot-notation and saves the change asynchronously."""
        if self.get(key) == value:
            return

        if (
            self.app_context
            and hasattr(self.app_context, "_state")
            and self.app_context._state is not None
        ):
            self.app_context.state.settings.set(key, value)
            self._settings = self.app_context.state.settings.to_dict()
            await self.app_context.storage.flush(self.app_context.state)
            return

        keys = key.split(".")
        d: Any = self._settings
        for k in keys[:-1]:
            if isinstance(d, dict):
                d = d.setdefault(k, {})
            else:
                raise ConfigurationError(
                    f"Cannot set key '{key}' because path conflict."
                )

        if isinstance(d, dict):
            d[keys[-1]] = value

        if key != "web.jwt_token_secret":
            logger.debug(
                f"Setting '{key}' updated to '{value}'. Saving configuration asynchronously."
            )
        else:
            logger.debug(
                f"Setting '{key}' updated. Saving configuration asynchronously."
            )

        assert self.db is not None
        async with self.db.session_manager() as db:
            await self._write_config(db)

    async def reload(self):
        """Reloads the settings from the database asynchronously."""
        logger.info("Reloading configuration from database asynchronously")
        await self.load()
        logger.info("Configuration reloaded successfully.")
