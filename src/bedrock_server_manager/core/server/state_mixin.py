# bedrock_server_manager/core/server/state_mixin.py
"""Provides the :class:`.ServerStateMixin` for the :class:`~.core.bedrock_server.BedrockServer` class.

This mixin is responsible for managing the persisted state of a Bedrock server
instance. This state includes its installed version, current operational status
(e.g., "RUNNING", "STOPPED"), target version for updates, and other custom
configuration values.

These states are stored in a server-specific JSON configuration file, typically
named ``<server_name>_config.json``, located within the server's dedicated
configuration directory (see :meth:`.BedrockServerBaseMixin.server_config_dir`).
The structure of this JSON file is managed by this mixin, including schema
versioning (see :const:`.SERVER_CONFIG_SCHEMA_VERSION`) and migration from
older formats.

Additionally, this mixin handles reading essential dynamic properties from the
server's live ``server.properties`` file, such as the world name (`level-name`).

Key functionalities:
    - Loading and saving the server-specific JSON configuration.
    - Migrating older server configuration formats to the current schema.
    - Providing getter and setter methods for various state attributes like
      installed version, target version, status, and custom key-value pairs.
    - Reading the world name from ``server.properties``.
    - Reconciling actual server runtime status with stored status.

"""
import os
import json
from typing import Optional, Any, Dict, TYPE_CHECKING

# Local application imports.
from bedrock_server_manager.core.server.base_server_mixin import BedrockServerBaseMixin
from bedrock_server_manager.error import (
    MissingArgumentError,
    UserInputError,
    FileOperationError,
    ConfigParseError,
    AppFileNotFoundError,
)

# Version for the server-specific JSON config schema
SERVER_CONFIG_SCHEMA_VERSION: int = 2
"""The schema version for the server-specific JSON configuration file.
This version number is stored within the JSON file itself (e.g., in
``<server_name>_config.json`` under the key ``config_schema_version``).
It's used by :meth:`.ServerStateMixin._load_server_config` and
:meth:`.ServerStateMixin._migrate_server_config_v1_to_v2` to determine if
a configuration file needs migration from an older format.
Currently, version 2 represents a nested structure, while older (v1) configs
were flat and lacked a version key.
"""


class ServerStateMixin(BedrockServerBaseMixin):
    """Manages persistent state and configuration for a Bedrock server instance.

    This mixin extends :class:`.BedrockServerBaseMixin` and is responsible for
    handling the server's specific configuration, which is stored in a JSON file
    (e.g., ``<server_name>_config.json``). This configuration includes details
    such as the installed server version, target version for updates, current
    operational status (e.g., "RUNNING", "STOPPED"), autoupdate settings, and
    any custom key-value pairs defined by the user or other parts of the application.

    Key responsibilities:
        - Loading the server-specific JSON configuration file upon initialization,
          creating it with defaults if it doesn't exist.
        - Handling migration of the server JSON configuration from older schema
          versions (e.g., v1 flat structure to v2 nested structure).
        - Providing a centralized method (:meth:`._manage_json_config`) for reading
          and writing values to the JSON configuration using dot-notation for keys.
        - Offering public getter and setter methods for common state properties
          (version, status, target version, autoupdate, custom values).
        - Reading the server's world name (``level-name``) directly from its
          ``server.properties`` file.
        - Reconciling the server's actual runtime status (obtained from other mixins)
          with the status stored in its configuration file.

    It relies on attributes initialized in :class:`.BedrockServerBaseMixin`, such
    as `server_name` and `server_config_dir`, to locate and manage its files.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initializes the ServerStateMixin.

        This constructor primarily calls ``super().__init__(*args, **kwargs)``
        to ensure correct initialization within a cooperative multiple inheritance
        setup. It assumes that attributes from :class:`.BedrockServerBaseMixin`
        (like `server_name`, `logger`, `server_config_dir`) are already
        initialized or will be by a preceding class in the MRO.
        """
        super().__init__(*args, **kwargs)

    @property
    def _server_specific_json_config_file_path(self) -> str:
        """str: The absolute path to this server's specific JSON configuration file.

        The filename is typically ``<server_name>_config.json``, located within
        the directory returned by :attr:`.BedrockServerBaseMixin.server_config_dir`.
        """
        return os.path.join(self.server_config_dir, f"{self.server_name}_config.json")

    def _get_default_server_config(self) -> Dict[str, Any]:
        """Returns the default structure and values for a server's JSON config file.

        This structure is used when a server's configuration file is first created
        or when migrating from an older, unrecognized format. It includes the
        current :const:`.SERVER_CONFIG_SCHEMA_VERSION`.

        Returns:
            Dict[str, Any]: A dictionary representing the default server configuration.
            The structure includes keys like "config_schema_version", "server_info"
            (with "installed_version", "status"), "settings" (with "autoupdate",
            "target_version"), and an empty "custom" dictionary.
        """
        return {
            "config_schema_version": SERVER_CONFIG_SCHEMA_VERSION,
            "server_info": {
                "installed_version": "UNKNOWN",
                "status": "UNKNOWN",
            },
            "settings": {
                "autoupdate": False,  # Default to boolean
                "target_version": "UNKNOWN",
            },
            "custom": {},
        }

    def _migrate_server_config_v1_to_v2(
        self, old_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Migrates a flat v1 server configuration to the nested v2 format.

        This internal method takes an old, presumably flat dictionary
        (`old_config`) representing a v1 server configuration and transforms
        it into the structured v2 format defined by
        :meth:`._get_default_server_config`. Known v1 keys like
        "installed_version", "target_version", "status", and "autoupdate"
        are mapped to their new locations in the "server_info" and "settings"
        sections. Any other unrecognized keys from the old config are moved
        into a "custom" sub-dictionary.

        Args:
            old_config (Dict[str, Any]): The dictionary loaded from an old v1
                server configuration file.

        Returns:
            Dict[str, Any]: A new dictionary representing the server configuration
            in the v2 schema, populated with values from the `old_config`.
        """
        self.logger.info(
            f"Migrating server config for '{self.server_name}' from v1 (flat) to v2 (nested)."
        )
        new_config = self._get_default_server_config()  # Start with a clean v2 default

        # Migrate known server_info keys
        new_config["server_info"]["installed_version"] = old_config.get(
            "installed_version", new_config["server_info"]["installed_version"]
        )
        # Note: target_version was in top-level in v1, moved to settings in v2 structure.
        # The default config already provides a 'UNKNOWN' if not found.
        new_config["settings"]["target_version"] = old_config.get(
            "target_version", new_config["settings"]["target_version"]
        )
        new_config["server_info"]["status"] = old_config.get(
            "status", new_config["server_info"]["status"]
        )

        # Migrate known settings keys
        autoupdate_val = old_config.get("autoupdate")
        if isinstance(
            autoupdate_val, str
        ):  # v1 might have stored as string "true"/"false"
            new_config["settings"]["autoupdate"] = autoupdate_val.lower() == "true"
        elif isinstance(autoupdate_val, bool):  # Or correctly as bool
            new_config["settings"]["autoupdate"] = autoupdate_val
        # If missing or other type, it keeps the default from _get_default_server_config()

        # Migrate any other unrecognized top-level keys to the "custom" section
        known_v1_keys_handled = {
            "installed_version",
            "target_version",  # Already handled for its new location
            "status",
            "autoupdate",
            # config_schema_version is not a v1 key, but good to exclude if it somehow appears
            "config_schema_version",
        }
        for key, value in old_config.items():
            if key not in known_v1_keys_handled:
                new_config["custom"][key] = value

        new_config["config_schema_version"] = (
            SERVER_CONFIG_SCHEMA_VERSION  # Ensure new version is set
        )
        return new_config

    def _load_server_config(self) -> Dict[str, Any]:
        """Loads the server-specific JSON configuration.

        This method handles:
            -   Ensuring the server's configuration directory exists.
            -   Creating a default configuration file (using :meth:`._get_default_server_config`)
                if one does not exist.
            -   Reading the JSON content if the file exists.
            -   Handling empty or malformed JSON files by initializing with defaults
                and attempting migration if necessary.
            -   Checking the ``config_schema_version`` and triggering migration
                (via :meth:`._migrate_server_config_v1_to_v2`) if an older schema
                (specifically v1, identified by lack of version key) is detected.
                The migrated configuration is then saved.

        Returns:
            Dict[str, Any]: The loaded (and potentially migrated) server configuration
            as a dictionary.

        Raises:
            FileOperationError: If directory creation or file reading fails due
                to ``OSError``.
        """
        config_file_path = self._server_specific_json_config_file_path
        server_json_config_subdir = self.server_config_dir  # From base mixin

        try:
            os.makedirs(server_json_config_subdir, exist_ok=True)
        except OSError as e:
            raise FileOperationError(
                f"Failed to create server config directory '{server_json_config_subdir}': {e}"
            ) from e

        if not os.path.exists(config_file_path):
            self.logger.info(
                f"Server config file '{config_file_path}' not found. Initializing with defaults."
            )
            default_config = self._get_default_server_config()
            self._save_server_config(default_config)  # Save the new default config
            return default_config

        current_config: Dict[str, Any]
        try:
            with open(config_file_path, "r", encoding="utf-8") as f:
                content = f.read()
                if not content.strip():  # Handle empty file case
                    self.logger.warning(
                        f"Server config file '{config_file_path}' is empty. Re-initializing with defaults."
                    )
                    current_config = self._get_default_server_config()
                    self._save_server_config(current_config)
                    return current_config

                loaded_json = json.loads(content)
                if not isinstance(loaded_json, dict):
                    # This case implies a severely malformed file, not just old schema.
                    # Attempting migration might be risky. Let's log and re-initialize.
                    self.logger.error(
                        f"Server config file '{config_file_path}' content is not a JSON object (dictionary). "
                        "The file is likely corrupted. Re-initializing with defaults."
                    )
                    current_config = self._get_default_server_config()
                    self._save_server_config(current_config)
                    return current_config
                current_config = loaded_json

        except json.JSONDecodeError as e_json:
            self.logger.warning(
                f"Failed to parse JSON from '{config_file_path}': {e_json}. "
                "File might be corrupted or in an unknown format. Re-initializing with defaults."
            )
            current_config = self._get_default_server_config()
            self._save_server_config(current_config)
            return current_config
        except OSError as e_os:
            raise FileOperationError(
                f"Failed to read config file '{config_file_path}': {e_os}"
            ) from e_os

        # Schema version check and migration for v1 (no version key)
        if "config_schema_version" not in current_config:
            self.logger.info(
                f"Old server config format (v1, no schema version) detected in '{config_file_path}'. Migrating to v{SERVER_CONFIG_SCHEMA_VERSION}."
            )
            current_config = self._migrate_server_config_v1_to_v2(current_config)
            self._save_server_config(current_config)  # Save migrated config
        elif (
            current_config.get("config_schema_version") != SERVER_CONFIG_SCHEMA_VERSION
        ):
            # Placeholder for future schema migrations (e.g., v2 to v3)
            # For now, if it's not v1 (handled above) and not current, log a warning.
            self.logger.warning(
                f"Server config schema version mismatch in '{config_file_path}'. "
                f"Found version {current_config.get('config_schema_version')}, expected {SERVER_CONFIG_SCHEMA_VERSION}. "
                "Attempting to use as is, but data might be incompatible or migration not yet supported."
            )
            # Potentially, one might add specific migration paths here:
            # if current_config.get("config_schema_version") == 2 and SERVER_CONFIG_SCHEMA_VERSION == 3:
            #     current_config = self._migrate_server_config_v2_to_v3(current_config)
            #     self._save_server_config(current_config)

        return current_config

    def _save_server_config(self, config_data: Dict[str, Any]) -> None:
        """Saves the server configuration data to its JSON file.

        The configuration is pretty-printed with an indent of 4 and sorted keys.

        Args:
            config_data (Dict[str, Any]): The server configuration dictionary to save.

        Raises:
            FileOperationError: If writing the configuration file fails due to an ``OSError``.
            ConfigParseError: If `config_data` is not JSON serializable (``TypeError``).
        """
        config_file_path = self._server_specific_json_config_file_path
        try:
            with open(config_file_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=4, sort_keys=True)
            self.logger.debug(
                f"Successfully wrote server config to '{config_file_path}'."
            )
        except OSError as e:
            raise FileOperationError(
                f"Failed to write server config file '{config_file_path}': {e}"
            ) from e
        except TypeError as e_type:  # For non-serializable data
            raise ConfigParseError(
                f"Server config data for '{self.server_name}' is not JSON serializable: {e_type}"
            ) from e_type

    def _manage_json_config(
        self,
        key: str,
        operation: str,
        value: Any = None,
    ) -> Optional[Any]:
        """Centralized helper to read/write to the server's JSON config using dot-notation.

        This method handles loading the current configuration (including any necessary
        migrations via :meth:`._load_server_config`), then performs the specified
        `operation` ("read" or "write") on the configuration data.

        For "read" operations, it navigates the nested dictionary structure using
        the dot-separated `key` (e.g., "server_info.status").
        For "write" operations, it sets the `value` at the location specified by `key`,
        creating intermediate dictionaries if they don't exist. After a "write",
        the entire configuration is saved back to the file via :meth:`._save_server_config`.

        Args:
            key (str): The dot-separated key indicating the path to the value within
                the JSON structure (e.g., "server_info.installed_version", "custom.my_setting").
            operation (str): The operation to perform, either "read" or "write"
                (case-insensitive).
            value (Any, optional): The value to set if the `operation` is "write".
                Ignored for "read". Defaults to ``None``.

        Returns:
            Optional[Any]: For "read" operations, returns the retrieved value if the
            key exists, otherwise ``None``. For "write" operations, always returns ``None``.

        Raises:
            MissingArgumentError: If `key` is empty.
            UserInputError: If `operation` is not "read" or "write".
            ConfigParseError: If, during a "write" operation, an intermediate part
                of the `key` path refers to a non-dictionary item, preventing
                further nesting.
            FileOperationError: Propagated from :meth:`._load_server_config` or
                :meth:`._save_server_config` if file I/O fails.
        """
        if not key:  # isinstance check for key?
            raise MissingArgumentError("Config key cannot be empty.")
        operation_lower = str(operation).lower()
        if operation_lower not in ["read", "write"]:
            raise UserInputError(
                f"Invalid operation: '{operation}'. Must be 'read' or 'write'."
            )

        current_config = self._load_server_config()

        if operation_lower == "read":
            d = current_config
            try:
                for k_part in key.split("."):
                    if not isinstance(d, dict):  # Ensure intermediate path is dict
                        self.logger.debug(
                            f"Server Config Read: Key='{key}', part '{k_part}' is not a dictionary. Path invalid."
                        )
                        return None
                    d = d[k_part]
                self.logger.debug(
                    f"Server Config Read: Key='{key}', Value='{d}' for '{self.server_name}'"
                )
                return d
            except KeyError:  # Key part not found
                self.logger.debug(
                    f"Server Config Read: Key='{key}' not found for '{self.server_name}'. Returning None."
                )
                return None
            except TypeError:  # Should be caught by isinstance above, but as fallback
                self.logger.debug(
                    f"Server Config Read: Key='{key}', path invalid (non-dict intermediate) for '{self.server_name}'. Returning None."
                )
                return None

        # Operation is "write"
        self.logger.debug(
            f"Server Config Write: Key='{key}', New Value='{value}' for '{self.server_name}'"
        )

        d = current_config
        keys_list = key.split(".")
        for k_part in keys_list[:-1]:  # Navigate to the parent dictionary
            # Ensure d is a dict before calling setdefault. If not, it's an error.
            if not isinstance(d, dict):
                raise ConfigParseError(
                    f"Cannot create nested key '{key}': part '{k_part}' conflicts with existing non-dictionary value in config for '{self.server_name}'."
                )
            d = d.setdefault(k_part, {})
            # After setdefault, if the new d is not a dict (e.g. if setdefault returned a non-dict default, though it shouldn't here), error out.
            if not isinstance(d, dict):
                raise ConfigParseError(
                    f"Cannot create nested key '{key}': part '{k_part}' resulted in a non-dictionary in config for '{self.server_name}'."
                )

        # Ensure the final parent is a dictionary before setting the key
        if not isinstance(d, dict):
            raise ConfigParseError(
                f"Cannot set key '{keys_list[-1]}' in path '{'.'.join(keys_list[:-1])}': parent is not a dictionary in config for '{self.server_name}'."
            )
        d[keys_list[-1]] = value

        self._save_server_config(current_config)
        return None  # Explicitly return None for write operations

    def get_version(self) -> str:
        """Retrieves the 'installed_version' from the server's JSON config.

        Accesses ``server_info.installed_version`` via :meth:`._manage_json_config`.

        Returns:
            str: The installed version string, or "UNKNOWN" if not set or on error.
        """
        self.logger.debug(f"Getting installed version for server '{self.server_name}'.")
        try:
            version = self._manage_json_config(
                key="server_info.installed_version", operation="read"
            )
            return str(version) if version is not None else "UNKNOWN"
        except Exception as e:
            self.logger.error(
                f"Error getting version for '{self.server_name}': {e}", exc_info=True
            )
            return "UNKNOWN"

    def set_version(self, version_string: str) -> None:
        """Sets the 'installed_version' in the server's JSON config.

        Updates ``server_info.installed_version`` via :meth:`._manage_json_config`.

        Args:
            version_string (str): The version string to set (e.g., "1.20.30.02").

        Raises:
            UserInputError: If `version_string` is not a string.
        """
        self.logger.debug(
            f"Setting installed version for '{self.server_name}' to '{version_string}'."
        )
        if not isinstance(version_string, str):
            raise UserInputError(
                f"Version for '{self.server_name}' must be a string, got {type(version_string).__name__}."
            )
        self._manage_json_config(
            key="server_info.installed_version", operation="write", value=version_string
        )
        self.logger.info(f"Version for '{self.server_name}' set to '{version_string}'.")

    def get_autoupdate(self) -> bool:
        """Retrieves the 'autoupdate' setting from the server's JSON config.

        Accesses ``settings.autoupdate`` via :meth:`._manage_json_config`.

        Returns:
            bool: The autoupdate status (``True`` or ``False``). Defaults to ``False``
            if the setting is not found or an error occurs during retrieval.
        """
        self.logger.debug(f"Getting autoupdate value for server '{self.server_name}'.")
        try:
            autoupdate_setting = self._manage_json_config(
                key="settings.autoupdate", operation="read"
            )
            if isinstance(autoupdate_setting, bool):
                return autoupdate_setting
            # Handle string "true"/"false" for robustness if manually edited or from old versions
            if isinstance(autoupdate_setting, str):
                return autoupdate_setting.lower() == "true"
            self.logger.warning(
                f"Autoupdate setting for '{self.server_name}' is not a boolean, found: {autoupdate_setting}. Defaulting to False."
            )
            return False  # Default if not found or invalid type
        except Exception as e:
            self.logger.error(
                f"Error getting autoupdate setting for '{self.server_name}': {e}. Defaulting to False.",
                exc_info=True,
            )
            return False

    def set_autoupdate(self, value: bool) -> None:
        """Sets the 'autoupdate' setting in the server's JSON config.

        Updates ``settings.autoupdate`` via :meth:`._manage_json_config`.

        Args:
            value (bool): The boolean value to set for autoupdate.

        Raises:
            UserInputError: If `value` is not a boolean.
        """
        self.logger.debug(f"Setting autoupdate for '{self.server_name}' to '{value}'.")
        if not isinstance(value, bool):
            raise UserInputError(
                f"Autoupdate value for '{self.server_name}' must be a boolean, got {type(value).__name__}."
            )
        self._manage_json_config(
            key="settings.autoupdate", operation="write", value=value
        )
        self.logger.info(f"Autoupdate for '{self.server_name}' set to '{value}'.")

    def get_status_from_config(self) -> str:
        """Retrieves the stored 'status' from the server's JSON config.

        Accesses ``server_info.status`` via :meth:`._manage_json_config`. This
        reflects the last known status written to the config, not necessarily
        the live process status. For live status, use :meth:`.get_status`.

        Returns:
            str: The stored status string (e.g., "RUNNING", "STOPPED"), or
            "UNKNOWN" if not set or on error.
        """
        self.logger.debug(
            f"Getting stored status for '{self.server_name}' from JSON config."
        )
        try:
            status = self._manage_json_config(
                key="server_info.status", operation="read"
            )
            return str(status) if status is not None else "UNKNOWN"
        except Exception as e:
            self.logger.error(
                f"Error getting status from JSON config for '{self.server_name}': {e}",
                exc_info=True,
            )
            return "UNKNOWN"

    def set_status_in_config(self, status_string: str) -> None:
        """Sets the 'status' in the server's JSON config.

        Updates ``server_info.status`` via :meth:`._manage_json_config`. This is
        used to persist the server's state.

        Args:
            status_string (str): The status string to set (e.g., "RUNNING", "STOPPED").

        Raises:
            UserInputError: If `status_string` is not a string.
        """
        self.logger.debug(
            f"Setting status in JSON config for '{self.server_name}' to '{status_string}'."
        )
        if not isinstance(status_string, str):
            raise UserInputError(
                f"Status for '{self.server_name}' must be a string, got {type(status_string).__name__}."
            )
        self._manage_json_config(
            key="server_info.status", operation="write", value=status_string
        )
        self.logger.info(
            f"Status in JSON config for '{self.server_name}' set to '{status_string}'."
        )

    def get_target_version(self) -> str:
        """Retrieves the 'target_version' from the server's JSON config.

        Accesses ``settings.target_version`` (note: schema v2 location) via
        :meth:`._manage_json_config`. This indicates the version the server aims
        to be on, often "LATEST" or a specific version string.

        Returns:
            str: The target version string, or "LATEST" if not set or on error.
        """
        self.logger.debug(
            f"Getting stored target_version for '{self.server_name}' from JSON config."
        )
        try:
            # Path changed in v2 schema to settings.target_version
            version = self._manage_json_config(
                key="settings.target_version", operation="read"
            )
            return (
                str(version)
                if version is not None and str(version).strip()
                else "LATEST"
            )
        except Exception as e:
            self.logger.error(
                f"Error getting target_version from config for '{self.server_name}': {e}. Defaulting to LATEST.",
                exc_info=True,
            )
            return "LATEST"

    def set_target_version(self, version_string: str) -> None:
        """Sets the 'target_version' in the server's JSON config.

        Updates ``settings.target_version`` (note: schema v2 location) via
        :meth:`._manage_json_config`.

        Args:
            version_string (str): The target version string to set (e.g., "LATEST", "1.20.30.02").

        Raises:
            UserInputError: If `version_string` is not a string.
        """
        self.logger.debug(
            f"Setting target_version for '{self.server_name}' to '{version_string}'."
        )
        if not isinstance(version_string, str):
            raise UserInputError(
                f"target_version for '{self.server_name}' must be a string, got {type(version_string).__name__}."
            )
        # Path changed in v2 schema to settings.target_version
        self._manage_json_config(
            key="settings.target_version", operation="write", value=version_string
        )
        self.logger.info(
            f"target_version for '{self.server_name}' set to '{version_string}'."
        )

    def get_custom_config_value(self, key: str) -> Optional[Any]:
        """Retrieves a custom value from the 'custom' section of the server's JSON config.

        Accesses ``custom.<key>`` via :meth:`._manage_json_config`.

        Args:
            key (str): The key of the custom value to retrieve.

        Returns:
            Optional[Any]: The retrieved custom value, or ``None`` if the key
            is not found or an error occurs.

        Raises:
            UserInputError: If `key` is not a non-empty string.
        """
        self.logger.debug(
            f"Getting custom config key '{key}' for server '{self.server_name}'."
        )
        if not isinstance(key, str) or not key:
            raise UserInputError(
                f"Key for custom config on '{self.server_name}' must be a non-empty string."
            )
        full_key = f"custom.{key}"
        value = self._manage_json_config(key=full_key, operation="read")
        self.logger.debug(
            f"Retrieved custom config for '{self.server_name}': Key='{key}', Value='{value}'."
        )
        return value

    def set_custom_config_value(self, key: str, value: Any) -> None:
        """Sets a custom key-value pair in the 'custom' section of the server's JSON config.

        Updates ``custom.<key>`` via :meth:`._manage_json_config`.

        Args:
            key (str): The key for the custom value.
            value (Any): The value to set. Must be JSON serializable.

        Raises:
            UserInputError: If `key` is not a non-empty string.
            ConfigParseError: If `value` is not JSON serializable (from underlying save).
        """
        self.logger.debug(
            f"Setting custom config for '{self.server_name}': Key='{key}', Value='{value}'."
        )
        if not isinstance(key, str) or not key:
            raise UserInputError(
                f"Key for custom config on '{self.server_name}' must be a non-empty string."
            )
        full_key = f"custom.{key}"
        self._manage_json_config(key=full_key, operation="write", value=value)
        self.logger.info(
            f"Custom config for '{self.server_name}' set: Key='{key}', Value='{value}'."
        )

    @property
    def server_properties_path(self) -> str:
        """str: The absolute path to this server's ``server.properties`` file.

        This is constructed by joining :attr:`.BedrockServerBaseMixin.server_dir`
        with "server.properties".
        """
        return os.path.join(self.server_dir, "server.properties")

    def get_world_name(self) -> str:
        """Reads the ``level-name`` property from the server's ``server.properties`` file.

        Returns:
            str: The name of the world as specified in ``server.properties``.

        Raises:
            AppFileNotFoundError: If the ``server.properties`` file does not exist
                at the expected path (:attr:`.server_properties_path`).
            ConfigParseError: If the file cannot be read (e.g., due to permissions)
                or if the ``level-name`` key is missing, malformed, or has an empty value.
        """
        self.logger.debug(
            f"Reading world name for server '{self.server_name}' from: {self.server_properties_path}"
        )
        if not os.path.isfile(self.server_properties_path):
            raise AppFileNotFoundError(
                self.server_properties_path, "server.properties file"
            )

        try:
            with open(self.server_properties_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("level-name="):
                        parts = line.split("=", 1)
                        if len(parts) == 2 and parts[1].strip():
                            world_name = parts[1].strip()
                            self.logger.debug(
                                f"Found world name (level-name): '{world_name}' for '{self.server_name}'"
                            )
                            return world_name
                        else:  # Found level-name= but no value or only whitespace
                            raise ConfigParseError(
                                f"'level-name' property malformed or has empty value in {self.server_properties_path}"
                            )
        except OSError as e_os:  # Changed from generic OSError to be more specific
            raise ConfigParseError(
                f"Failed to read server.properties for '{self.server_name}': {e_os}"
            ) from e_os

        # This is reached if the loop completes without finding "level-name=".
        raise ConfigParseError(
            f"'level-name' property not found in {self.server_properties_path}"
        )

    def get_status(self) -> str:
        """Determines and returns the current reconciled operational status of the server.

        This method attempts to determine if the server process is actually running
        (by calling ``self.is_running()``, which is expected to be provided by
        another mixin like ``ProcessMixin``). It then compares this live status
        with the status stored in the server's JSON configuration file
        (retrieved via :meth:`.get_status_from_config`).

        If a discrepancy is found (e.g., process is running but config says "STOPPED",
        or vice-versa when config said "RUNNING"), it updates the stored status in
        the JSON config to reflect the actual state.

        Returns:
            str: The reconciled operational status of the server as a string
            (e.g., "RUNNING", "STOPPED"). If ``self.is_running()`` is not available
            or fails, it falls back to returning the last known status from config.
        """
        self.logger.debug(
            f"Determining overall status for server '{self.server_name}'."
        )

        actual_is_running = False
        try:
            # This method is expected to be provided by ServerProcessMixin.
            if not hasattr(self, "is_running"):
                self.logger.warning(
                    "is_running method not found. Falling back to stored config status."
                )
                return self.get_status_from_config()
            actual_is_running = self.is_running()
        except Exception as e_is_running_check:
            self.logger.error(
                f"Error calling self.is_running() for '{self.server_name}': {e_is_running_check}. Fallback to stored status."
            )
            return self.get_status_from_config()

        stored_status = self.get_status_from_config()
        final_status = "UNKNOWN"  # Default

        if actual_is_running:
            final_status = "RUNNING"
            # If there's a discrepancy, update the stored status.
            if stored_status != "RUNNING":
                self.logger.info(
                    f"Server '{self.server_name}' is running. Updating stored status from '{stored_status}' to RUNNING."
                )
                try:
                    self.set_status_in_config("RUNNING")
                except Exception as e_set_cfg:
                    self.logger.warning(
                        f"Failed to update stored status to RUNNING for '{self.server_name}': {e_set_cfg}"
                    )
        else:  # Not actually running.
            # If config thought it was running, correct it.
            if stored_status == "RUNNING":
                self.logger.info(
                    f"Server '{self.server_name}' not running but stored status was RUNNING. Updating to STOPPED."
                )
                final_status = "STOPPED"
                try:
                    self.set_status_in_config("STOPPED")
                except Exception as e_set_cfg:
                    self.logger.warning(
                        f"Failed to update stored status to STOPPED for '{self.server_name}': {e_set_cfg}"
                    )
            elif (
                stored_status == "UNKNOWN"
            ):  # If actual is not running and stored is unknown
                final_status = "STOPPED"
            else:  # Trust other stored statuses like UPDATING, ERROR, STARTING, STOPPING etc.
                final_status = stored_status

        self.logger.debug(
            f"Final determined status for '{self.server_name}': {final_status}"
        )
        return final_status
