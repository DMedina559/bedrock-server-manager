# bedrock_server_manager/config/settings.py
"""Manages application-wide configuration settings.

This module provides the `Settings` class, which is responsible for loading
settings from a JSON file, providing default values for missing keys, saving
changes back to the file, and determining the appropriate application data and
configuration directories based on the environment.

The configuration is stored in a nested JSON format. Settings are accessed
programmatically using dot-notation (e.g., :meth:`Settings.get('paths.servers')`).

Key components:

    - :class:`Settings`: The main class for managing configuration.
    - :func:`deep_merge`: A utility function for merging dictionaries.
    - `settings`: A global instance of the :class:`Settings` class.

"""

import os
import json
import logging
import collections.abc
from typing import Any, Dict, Mapping

from bedrock_server_manager.error import ConfigurationError
from bedrock_server_manager.config.const import (
    package_name,
    env_name,
    get_installed_version,
)

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
            # Ensure the destination node is a dictionary before merging
            node = destination.setdefault(key, {})
            if not isinstance(node, collections.abc.Mapping):
                # If the destination node exists but is not a dictionary,
                # overwrite it with the source dictionary node
                node = {}
                destination[key] = node
            deep_merge(value, node)
        else:
            destination[key] = value
    return destination


class Settings:
    """Manages loading, accessing, and saving application settings.

    This class acts as a single source of truth for all configuration data.
    It handles:

        - Determining appropriate application data and configuration directories
          based on the environment (respecting ``BSM_DATA_DIR``).
        - Loading settings from a JSON configuration file (``bedrock_server_manager.json``).
        - Providing sensible default values for missing settings.
        - Migrating settings from older formats (e.g., ``script_config.json`` or schema v1).
        - Saving changes back to the configuration file.
        - Ensuring critical directories (e.g., for servers, backups, logs) exist.

    Settings are stored in a nested dictionary structure and can be accessed
    programmatically using dot-notation via the :meth:`get` and :meth:`set` methods
    (e.g., ``settings.get('paths.servers')``).

    A global instance of this class, named `settings`, is typically used throughout
    the application.

    Attributes:
        config_file_name (str): The name of the configuration file.
        config_path (str): The full path to the configuration file.
    """

    def __init__(self):
        """Initializes the Settings object.

        This constructor performs the following actions:

            1. Determines the application's primary data and configuration directories.
            2. Handles migration of the configuration file name from the old
               `script_config.json` to `bedrock_server_manager.json` if necessary.
            3. Retrieves the installed package version.
            4. Loads settings from the configuration file. If the file doesn't exist,
               it's created with default settings. If an old configuration schema is
               detected, it's migrated.
            5. Ensures all necessary application directories (e.g., for servers,
               backups, logs) exist on the filesystem.

        """
        logger.debug("Initializing Settings")
        # Determine the primary application data and config directories.
        self._app_data_dir_path = self._determine_app_data_dir()
        self._config_dir_path = self._determine_app_config_dir()
        self.config_file_name = NEW_CONFIG_FILE_NAME
        self._migrate_config_filename()
        self.config_path = os.path.join(self._config_dir_path, self.config_file_name)

        # Get the installed package version.
        self._version_val = get_installed_version()

        # Load settings from the config file or create a default one.
        self._settings: Dict[str, Any] = {}
        self.load()

    def _migrate_config_filename(self):
        """
        Checks for the old config filename and renames it to the new one.

        This is a one-time operation for existing installations that previously
        used `script_config.json`. If `script_config.json` exists and
        `bedrock_server_manager.json` does not, `script_config.json` will be
        renamed to `bedrock_server_manager.json`.

        Raises:
            ConfigurationError: If the renaming operation fails due to an OSError
                (e.g., permission issues).
        """
        old_config_path = os.path.join(self._config_dir_path, OLD_CONFIG_FILE_NAME)
        new_config_path = os.path.join(self._config_dir_path, NEW_CONFIG_FILE_NAME)

        if os.path.exists(old_config_path) and not os.path.exists(new_config_path):
            logger.info(
                f"Found old configuration file '{OLD_CONFIG_FILE_NAME}'. "
                f"Migrating to '{NEW_CONFIG_FILE_NAME}'..."
            )
            try:
                os.rename(old_config_path, new_config_path)
                logger.info(
                    "Successfully migrated configuration file name. "
                    f"The old file '{OLD_CONFIG_FILE_NAME}' has been renamed."
                )
            except OSError as e:
                raise ConfigurationError(
                    f"Failed to rename configuration file from '{old_config_path}' to "
                    f"'{new_config_path}'. Please check file permissions."
                ) from e

    def _determine_app_data_dir(self) -> str:
        """Determines the main application data directory.

        It prioritizes the ``BSM_DATA_DIR`` environment variable if set.
        Otherwise, it defaults to a ``bedrock-server-manager`` directory in the
        user's home folder (e.g., ``~/.bedrock-server-manager`` on Linux/macOS or
        ``%USERPROFILE%\\bedrock-server-manager`` on Windows).
        The directory is created if it doesn't exist.

        Returns:
            str: The absolute path to the application data directory.
        """
        env_var_name = f"{env_name}_DATA_DIR"
        data_dir = os.environ.get(env_var_name)
        if not data_dir:
            data_dir = os.path.join(os.path.expanduser("~"), f"{package_name}")
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
            "custom": {},
        }

    def load(self):
        """Loads settings from the JSON configuration file.

        The process is as follows:

            1. Starts with a fresh copy of the default settings (see :meth:`default_config`).
            2. If the configuration file (``bedrock_server_manager.json``) doesn't exist,
               it's created with these default settings.
            3. If the file exists, it's read:
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
        # Always start with a fresh copy of the defaults to build upon.
        self._settings = self.default_config

        if not os.path.exists(self.config_path):
            logger.info(
                f"Configuration file not found at {self.config_path}. "
                "Creating with default settings."
            )
            self._write_config()
        else:
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    user_config = json.load(f)

                # Check for old config format and migrate if necessary.
                if "config_version" not in user_config:
                    self._migrate_v1_to_v2(user_config)
                    # Reload config from the newly migrated file
                    with open(self.config_path, "r", encoding="utf-8") as f:
                        user_config = json.load(f)

                # Deep merge user settings into the default settings.
                deep_merge(user_config, self._settings)

            except (ValueError, OSError) as e:
                logger.warning(
                    f"Could not load config file at {self.config_path}: {e}. "
                    "Using default settings. A new config will be saved on the next settings change."
                )

        self._ensure_dirs_exist()

    def _migrate_v1_to_v2(self, old_config: dict):
        """Migrates a flat v1 configuration (no ``config_version`` key) to the nested v2 format.

        This method performs the following steps:

            1. Backs up the existing v1 configuration file to ``<config_file_name>.v1.bak``.
            2. Creates a new configuration structure based on :meth:`default_config`.
            3. Maps known keys from the old flat ``old_config`` dictionary to their
               new locations in the nested v2 structure.
            4. Sets ``config_version`` to ``CONFIG_SCHEMA_VERSION`` in the new structure.
            5. Writes the new v2 configuration to the primary configuration file.

        Args:
            old_config (dict): The loaded dictionary from the old, flat (v1)
                configuration file.

        Raises:
            ConfigurationError: If backing up the old config file fails (e.g., due
                to file permissions).
        """
        logger.info(
            "Old configuration format (v1) detected. Migrating to new nested format (v2)..."
        )
        # 1. Back up the old file
        backup_path = f"{self.config_path}.v1.bak"
        try:
            os.rename(self.config_path, backup_path)
            logger.info(f"Old configuration file backed up to {backup_path}")
        except OSError as e:
            raise ConfigurationError(
                f"Failed to back up old config file to {backup_path}. "
                "Migration aborted. Please check file permissions."
            ) from e

        # 2. Create the new config by starting with defaults and overwriting with old values
        new_config = self.default_config
        key_map = {
            # Old Key: ("category", "new_key")
            "BASE_DIR": ("paths", "servers"),
            "CONTENT_DIR": ("paths", "content"),
            "DOWNLOAD_DIR": ("paths", "downloads"),
            "BACKUP_DIR": ("paths", "backups"),
            "PLUGIN_DIR": ("paths", "plugins"),
            "LOG_DIR": ("paths", "logs"),
            "BACKUP_KEEP": ("retention", "backups"),
            "DOWNLOAD_KEEP": ("retention", "downloads"),
            "LOGS_KEEP": ("retention", "logs"),
            "FILE_LOG_LEVEL": ("logging", "file_level"),
            "CLI_LOG_LEVEL": ("logging", "cli_level"),
            "WEB_PORT": ("web", "port"),
            "TOKEN_EXPIRES_WEEKS": ("web", "token_expires_weeks"),
        }
        for old_key, (category, new_key) in key_map.items():
            if old_key in old_config:
                new_config[category][new_key] = old_config[old_key]

        # 3. Save the new configuration file
        self._settings = new_config
        self._write_config()
        logger.info("Successfully migrated configuration to the new format.")

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
        ]
        for dir_path in dirs_to_check:
            if dir_path and isinstance(dir_path, str):
                try:
                    os.makedirs(dir_path, exist_ok=True)
                except OSError as e:
                    raise ConfigurationError(
                        f"Could not create critical directory: {dir_path}"
                    ) from e

    def _write_config(self):
        """Writes the current settings dictionary to the JSON configuration file.

        The settings are stored in the file specified by :attr:`config_path`.
        The parent directory for the config file is created if it doesn't exist.
        The JSON is pretty-printed with an indent of 4 and sorted keys.

        Raises:
            ConfigurationError: If writing the configuration fails (e.g., due to
                permission issues or an object that cannot be serialized to JSON).
        """
        try:
            os.makedirs(self._config_dir_path, exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self._settings, f, indent=4, sort_keys=True)
        except (OSError, TypeError) as e:
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
        path specified by `key`. The configuration is only written to disk via
        :meth:`_write_config` if the new ``value`` is different from the
        existing value for the given ``key``.

        Example:
            ``settings.set("retention.backups", 5)``
            This will update the "backups" key within the "retention" dictionary
            and then save the entire configuration to the file.

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
        logger.info(f"Setting '{key}' updated to '{value}'. Saving configuration.")
        self._write_config()

    def reload(self):
        """Reloads the settings from the configuration file.

        This method re-runs the :meth:`load` method, which re-reads the
        configuration file (specified by :attr:`config_path`) and updates the
        in-memory settings dictionary. Any external changes made to the file
        since the last load or save will be reflected.
        """
        logger.info(f"Reloading configuration from {self.config_path}")
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


# A singleton instance of the Settings class, used throughout the application.
settings = Settings()
"""The global singleton instance of the :class:`Settings` class.

This instance should be imported and used by other modules to access
application-wide configuration.

Example:
    >>> from bedrock_server_manager.config.settings import settings
    >>> server_path = settings.get("paths.servers")
"""
