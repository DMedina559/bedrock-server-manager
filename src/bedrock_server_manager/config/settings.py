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
        config_dir: Optional[str] = None,
        data_dir: Optional[str] = None,
    ):
        """Initializes the Settings object.

        This constructor performs the following actions:

            1. Determines the application's primary data and configuration directories.
            2. Retrieves the installed package version.
            3. Loads settings from the database. If the database is empty,
               it's created with default settings.
            4. Ensures all necessary application directories (e.g., for servers,
               backups, logs) exist on the filesystem.

        """
        logger.debug("Initializing Settings")
        self.db = db
        self._data_dir: Optional[str] = data_dir
        self._config_dir: Optional[str] = config_dir
        self._settings: Dict[str, Any] = {}

    @property
    def config_dir(self) -> str:
        """str: The absolute path to the application's configuration directory.

        This is determined by :meth:`_determine_app_config_dir`.
        Example: ``~/.bedrock-server-manager/.config``
        """
        if self._config_dir is None:
            from . import bcm_config

            config_dir = bcm_config.get_config_dir()

            return config_dir
        return self._config_dir

    @property
    def data_dir(self) -> str:
        """str: The absolute path to the application's main data directory.

        This is determined by :meth:`_determine_app_data_dir`.
        Example: ``~/.bedrock-server-manager``
        """
        if self._data_dir is None:
            from . import bcm_config

            config = bcm_config.load_config()
            data_dir = config["data_dir"]

            return str(data_dir)
        return self._data_dir

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

    def load(self) -> None:
        """Loads settings from the database.

        The process is as follows:

            1. Starts with a fresh copy of the default settings (see :meth:`default_config`).
            2. If the database is empty, it's populated with these default settings.
            3. If the database has settings, they are loaded:
                The loaded user settings are deeply merged on top of the default settings.
                This ensures that any new settings added in later application versions are present,
                while user-defined values are preserved.
            4. If any error occurs during loading (e.g., JSON decoding error, OS error),
               a warning is logged, and the application proceeds with default settings.
               The configuration will be saved with current (potentially default) settings
               on the next call to :meth:`set` or :meth:`_write_config`.
            5. Finally, :meth:`_ensure_dirs_exist` is called to create any missing
               critical application directories.

        """

        # Always start with a fresh copy of the defaults to build upon.
        self._settings = self.default_config

        assert self.db is not None
        with self.db.session_manager() as db:  # type: ignore
            # Check if the database is empty
            if db.query(Setting).count() == 0:
                logger.info(
                    "No settings found in the database. Creating with default settings."
                )
                self._write_config(db)
            else:
                try:
                    user_config: Dict[str, Any] = {}
                    for setting in db.query(Setting).all():
                        user_config[setting.key] = setting.value

                    # Deep merge user settings into the default settings.
                    deep_merge(user_config, self._settings)

                except (ValueError, OSError) as e:
                    logger.warning(
                        f"Could not load config from database: {e}. "
                        "Using default settings. A new config will be saved on the next settings change."
                    )

    def _write_config(self, db: Any) -> None:
        """Writes the current settings dictionary to the database.

        Raises:
            ConfigurationError: If writing the configuration fails (e.g., due to
                permission issues or an object that cannot be serialized to JSON).
        """
        try:
            for key, value in self._settings.items():
                setting = db.query(Setting).filter_by(key=key).first()
                if setting:
                    setting.value = value
                else:
                    setting = Setting(key=key, value=value)
                    db.add(setting)
            db.commit()
        except Exception as e:
            db.rollback()
            raise ConfigurationError(f"Failed to write configuration: {e}") from e

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieves a setting value using dot-notation for nested access.

        Example:
            ``settings.get("paths.servers")``
            ``settings.get("non_existent.key", "default_value")``

        Args:
            key (str): The dot-separated configuration key (e.g., "paths.servers").
            default (Any, optional): The value to return if the key is not found
                or if any part of the path does not exist. Defaults to None.

        Returns:
            Any: The value associated with the key, or the ``default`` value if
            the key is not found or an intermediate key is not a dictionary.
        """
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

    def set(self, key: str, value: Any) -> None:
        """Sets a configuration value using dot-notation and saves the change.

        Intermediate dictionaries are created if they do not exist along the
        path specified by `key`. The configuration is only written to the database via
        :meth:`_write_config` if the new ``value`` is different from the
        existing value for the given ``key``.

        Example:
            ``settings.set("retention.backups", 5)``
            This will update the "backups" key within the "retention" dictionary
            and then save the entire configuration to the database.

        Args:
            key (str): The dot-separated configuration key to set (e.g.,
                "retention.backups").
            value (Any): The value to associate with the key.
        """
        # Avoid writing to file if the value hasn't changed.
        if self.get(key) == value:
            return

        keys = key.split(".")
        d: Any = self._settings
        for k in keys[:-1]:
            if isinstance(d, dict):
                d = d.setdefault(k, {})
            else:
                # Should not happen if structure is maintained, but safety check
                raise ConfigurationError(
                    f"Cannot set key '{key}' because path conflict."
                )

        if isinstance(d, dict):
            d[keys[-1]] = value
        if key != "web.jwt_token_secret":
            logger.debug(f"Setting '{key}' updated to '{value}'. Saving configuration.")
        else:
            logger.debug(f"Setting '{key}' updated. Saving configuration.")
        assert self.db is not None
        with self.db.session_manager() as db:  # type: ignore
            self._write_config(db)

    def reload(self):
        """Reloads the settings from the database.

        This method re-runs the :meth:`load` method, which re-reads the
        configuration from the database and updates the
        in-memory settings dictionary. Any external changes made to the database
        since the last load or save will be reflected.
        """
        logger.info("Reloading configuration from database")
        self.load()
        logger.info("Configuration reloaded successfully.")
