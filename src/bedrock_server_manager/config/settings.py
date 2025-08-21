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

import os
import json
import logging
import collections.abc
from typing import Any, Dict, TYPE_CHECKING, Optional


if TYPE_CHECKING:
    from ..db.database import Database
from ..db.models import Setting, Base
from ..error import ConfigurationError
from .const import (
    package_name,
    env_name,
    app_author,
    get_installed_version,
)
from . import bcm_config

logger = logging.getLogger(__name__)

# The schema version for the configuration file. Used for migrations.
CONFIG_SCHEMA_VERSION = 2
NEW_CONFIG_FILE_NAME = "bedrock_server_manager.json"
OLD_CONFIG_FILE_NAME = "script_config.json"


def deep_merge(source: Dict[Any, Any], destination: Dict[Any, Any]) -> Dict[Any, Any]:
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
        if isinstance(value, collections.abc.Mapping):
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
        - Migrating settings from older formats (e.g., ``script_config.json`` or schema v1).
        - Saving changes back to the database.
        - Ensuring critical directories (e.g., for servers, backups, logs) exist.

    Settings are stored in a key-value format in the database and can be accessed
    programmatically using dot-notation via the :meth:`get` and :meth:`set` methods
    (e.g., ``settings.get('paths.servers')``).

    A global instance of this class, named `settings`, is typically used throughout
    the application.

    Attributes:
        config_file_name (str): The name of the configuration file.
        config_path (str): The full path to the configuration file.
    """

    def __init__(self, db: Optional["Database"] = None):
        """Initializes the Settings object.

        This constructor performs the following actions:

            1. Determines the application's primary data and configuration directories.
            2. Handles migration of the configuration file name from the old
               `script_config.json` to `bedrock_server_manager.json` if necessary.
            3. Retrieves the installed package version.
            4. Loads settings from the database. If the database is empty,
               it's created with default settings. If an old configuration schema is
               detected, it's migrated.
            5. Ensures all necessary application directories (e.g., for servers,
               backups, logs) exist on the filesystem.

        """
        logger.debug("Initializing Settings")
        self._app_data_dir_path = None
        self._config_dir_path = None
        self.config_file_name = NEW_CONFIG_FILE_NAME
        self.config_path = None
        self._version_val = get_installed_version()
        self._settings: Dict[str, Any] = {}
        self.db = db

    def _determine_app_data_dir(self) -> str:
        """Determines the main application data directory.

        It prioritizes the ``data_dir`` from bcm_config if set.
        Otherwise, it defaults to a ``bedrock-server-manager`` directory in the
        user's home folder (e.g., ``~/.bedrock-server-manager`` on Linux/macOS or
        ``%USERPROFILE%\\bedrock-server-manager`` on Windows).
        The directory is created if it doesn't exist.

        Returns:
            str: The absolute path to the application data directory.
        """
        # 1. Check config file
        config = bcm_config.load_config()
        data_dir = config["data_dir"]

        os.makedirs(data_dir, exist_ok=True)
        return data_dir

    def _determine_app_config_dir(self) -> str:
        """Determines the application's configuration directory.

        This directory is typically named ``.config`` and is nested within the main
        application data directory (determined by :meth:`_determine_app_data_dir`).
        For example, if the app data directory is ``~/.bedrock-server-manager``,
        the config directory will be ``~/.bedrock-server-manager/.config``.
        It is created if it doesn't exist.

        Returns:
            str: The absolute path to the application configuration directory.
        """
        config_dir = os.path.join(self._app_data_dir_path, ".config")
        os.makedirs(config_dir, exist_ok=True)
        return config_dir

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
                "config_version": CONFIG_SCHEMA_VERSION,
                "paths": {
                    "servers": "<app_data_dir>/servers",
                    "content": "<app_data_dir>/content",
                    "downloads": "<app_data_dir>/.downloads",
                    "backups": "<app_data_dir>/backups",
                    "plugins": "<app_data_dir>/plugins",
                    "logs": "<app_data_dir>/.logs",
                },
                "retention": {
                    "backups": 3,
                    "downloads": 3,
                    "logs": 3,
                },
                "logging": {
                    "file_level": logging.INFO,
                    "cli_level": logging.WARN,
                },
                "web": {
                    "host": "127.0.0.1",
                    "port": 11325,
                    "token_expires_weeks": 4,
                    "threads": 4,
                },
                "custom": {}
            }

        Returns:
            dict: A dictionary of default settings with a nested structure.
        """
        app_data_dir_val = self._app_data_dir_path
        return {
            "config_version": CONFIG_SCHEMA_VERSION,
            "paths": {
                "servers": os.path.join(app_data_dir_val, "servers"),
                "content": os.path.join(app_data_dir_val, "content"),
                "downloads": os.path.join(app_data_dir_val, ".downloads"),
                "backups": os.path.join(app_data_dir_val, "backups"),
                "plugins": os.path.join(app_data_dir_val, "plugins"),
                "logs": os.path.join(app_data_dir_val, ".logs"),
                "themes": os.path.join(app_data_dir_val, "themes"),
            },
            "retention": {
                "backups": 3,
                "downloads": 3,
                "logs": 3,
            },
            "logging": {
                "file_level": logging.INFO,
                "cli_level": logging.WARN,
            },
            "server_monitoring": {
                "player_log_monitoring_enabled": True,
                "player_log_monitoring_interval_sec": 60,
            },
            "web": {
                "host": "127.0.0.1",
                "port": 11325,
                "token_expires_weeks": 4,
                "threads": 4,
            },
            "custom": {},
        }

    def load(self):
        """Loads settings from the database.

        The process is as follows:

            1. Starts with a fresh copy of the default settings (see :meth:`default_config`).
            2. If the database is empty, it's populated with these default settings.
            3. If the database has settings, they are loaded:
                a. If the loaded configuration does not contain a ``config_version`` key,
                   it's assumed to be an old (v1) flat format and is migrated to the
                   current nested (v2) structure via :meth:`_migrate_v1_to_v2`. The
                   migrated config is then reloaded.
                b. The loaded user settings (either original v2 or migrated v1) are
                   deeply merged on top of the default settings. This ensures that
                   any new settings added in later application versions are present,
                   while user-defined values are preserved.
            4. If any error occurs during loading (e.g., JSON decoding error, OS error),
               a warning is logged, and the application proceeds with default settings.
               The configuration will be saved with current (potentially default) settings
               on the next call to :meth:`set` or :meth:`_write_config`.
            5. Finally, :meth:`_ensure_dirs_exist` is called to create any missing
               critical application directories.

        """
        # Determine the primary application data and config directories.
        self._app_data_dir_path = self._determine_app_data_dir()
        self._config_dir_path = self._determine_app_config_dir()
        self.config_path = os.path.join(self._config_dir_path, self.config_file_name)

        # Always start with a fresh copy of the defaults to build upon.
        self._settings = self.default_config

        assert self.db is not None
        with self.db.session_manager() as db:
            # Check if the database is empty
            if db.query(Setting).count() == 0:
                logger.info(
                    "No settings found in the database. Creating with default settings."
                )
                self._write_config(db)
            else:
                try:
                    user_config = {}
                    for setting in db.query(Setting).all():
                        user_config[setting.key] = setting.value

                    # Deep merge user settings into the default settings.
                    deep_merge(user_config, self._settings)

                except (ValueError, OSError) as e:
                    logger.warning(
                        f"Could not load config from database: {e}. "
                        "Using default settings. A new config will be saved on the next settings change."
                    )

        self._ensure_dirs_exist()

    def _ensure_dirs_exist(self):
        """Ensures that all critical directories specified in the settings exist.

        Iterates through the directory paths defined in ``paths`` section of the
        configuration (e.g., ``paths.servers``, ``paths.logs``) and creates them
        if they do not already exist.

        Raises:
            ConfigurationError: If a directory cannot be created (e.g., due to
                permission issues).
        """
        dirs_to_check = [
            self.get("paths.servers"),
            self.get("paths.content"),
            self.get("paths.downloads"),
            self.get("paths.backups"),
            self.get("paths.plugins"),
            self.get("paths.logs"),
            self.get("paths.themes"),
        ]
        for dir_path in dirs_to_check:
            if dir_path and isinstance(dir_path, str):
                try:
                    os.makedirs(dir_path, exist_ok=True)
                except OSError as e:
                    raise ConfigurationError(
                        f"Could not create critical directory: {dir_path}"
                    ) from e

    def _write_config(self, db: Any):
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
        d = self._settings
        try:
            for k in key.split("."):
                d = d[k]
            return d
        except (KeyError, TypeError):
            return default

    def set(self, key: str, value: Any):
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
        d = self._settings
        for k in keys[:-1]:
            d = d.setdefault(k, {})

        d[keys[-1]] = value
        if key != "web.jwt_token_secret":
            logger.info(f"Setting '{key}' updated to '{value}'. Saving configuration.")
        else:
            logger.info(f"Setting '{key}' updated. Saving configuration.")
        assert self.db is not None
        with self.db.session_manager() as db:
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

    @property
    def config_dir(self) -> str:
        """str: The absolute path to the application's configuration directory.

        This is determined by :meth:`_determine_app_config_dir`.
        Example: ``~/.bedrock-server-manager/.config``
        """
        return self._config_dir_path

    @property
    def app_data_dir(self) -> str:
        """str: The absolute path to the application's main data directory.

        This is determined by :meth:`_determine_app_data_dir`.
        Example: ``~/.bedrock-server-manager``
        """
        return self._app_data_dir_path

    @property
    def version(self) -> str:
        """str: The installed version of the ``bedrock_server_manager`` package.

        This is retrieved using ``get_installed_version()`` from
        ``bedrock_server_manager.config.const``.
        """
        return self._version_val
