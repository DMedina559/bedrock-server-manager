# bedrock_server_manager/core/server/state_mixin.py
"""Provides the :class:`.ServerStateMixin` for the :class:`~.core.bedrock_server.BedrockServer` class.

This mixin is responsible for managing the persisted state of a Bedrock server
instance. This state includes its installed version, current operational status
(e.g., "RUNNING", "STOPPED"), target version for updates, and other custom
configuration values.

These states are stored in a server-specific JSON configuration file, typically
named ``<server_name>_config.json``, located within the server's dedicated
configuration directory (see :meth:`.BedrockServerBaseMixin.server_config_dir`).
The structure of this configuration is managed by this mixin in the database.

Additionally, this mixin handles reading essential dynamic properties from the
server's live ``server.properties`` file, such as the world name (`level-name`).

Key functionalities:
    - Loading and saving the server-specific JSON configuration.
    - Providing getter and setter methods for various state attributes like
      installed version, target version, status, and custom key-value pairs.
    - Reading the world name from ``server.properties``.
    - Reconciling actual server runtime status with stored status.

"""

from typing import Any, Dict, Optional

import aiofiles.ospath

from ...db.models import Server
from ...error import (
    AppFileNotFoundError,
    ConfigParseError,
    MissingArgumentError,
    UserInputError,
)
from .base_server_mixin import BedrockServerBaseMixin


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
        setattr(self, "player_count", 0)
        setattr(self, "players", [])
        setattr(self, "_log_file_cursor", 0)
        setattr(self, "_scan_log_cursor", 0)

    def _get_default_server_config(self) -> Dict[str, Any]:
        """Returns the default structure and values for a server's JSON config file.

        This structure is used when a server's configuration file is first created
        or when migrating from an older, unrecognized format.         Returns:
            Dict[str, Any]: A dictionary representing the default server configuration.
            The structure includes keys like "server_info"
            (with "installed_version", "status"), "settings" (with "autoupdate",
            "target_version"), and an empty "custom" dictionary.
        """
        return {
            "server_info": {
                "installed_version": "UNKNOWN",
                "status": "UNKNOWN",
            },
            "settings": {
                "autoupdate": False,
                "autostart": False,
                "target_version": "UNKNOWN",
            },
            "custom": {},
        }

    async def _load_server_config(self) -> Dict[str, Any]:
        """Loads the server-specific JSON configuration asynchronously."""
        from sqlalchemy.future import select

        if self.settings.db is None:
            raise RuntimeError("Database connection not initialized.")

        async with self.settings.db.async_session_manager() as db:  # type: ignore
            result = await db.execute(
                select(Server).filter(Server.server_name == self.server_name)
            )
            server = result.scalars().first()

            if server:
                return {
                    "server_info": {
                        "installed_version": server.installed_version,
                        "status": server.status,
                    },
                    "settings": {
                        "autoupdate": server.autoupdate,
                        "autostart": server.autostart,
                        "target_version": server.target_version,
                    },
                    "custom": dict(server.custom) if server.custom is not None else {},
                }

            # Create new server config in DB
            self.logger.info(
                f"Server config for '{self.server_name}' not found in database. Initializing with defaults."
            )
            default_config = self._get_default_server_config()
            server = Server(
                server_name=self.server_name,
                installed_version=default_config["server_info"]["installed_version"],
                status=default_config["server_info"]["status"],
                autoupdate=default_config["settings"]["autoupdate"],
                autostart=default_config["settings"]["autostart"],
                target_version=default_config["settings"]["target_version"],
                custom=default_config["custom"],
            )
            db.add(server)
            await db.commit()
            await db.refresh(server)

            return {
                "server_info": {
                    "installed_version": server.installed_version,
                    "status": server.status,
                },
                "settings": {
                    "autoupdate": server.autoupdate,
                    "autostart": server.autostart,
                    "target_version": server.target_version,
                },
                "custom": dict(server.custom) if server.custom is not None else {},
            }

    async def _save_server_config(self, config_data: Dict[str, Any]) -> None:
        """Saves the server configuration data to the database asynchronously."""
        from sqlalchemy.future import select

        if self.settings.db is None:
            raise RuntimeError("Database connection not initialized.")

        async with self.settings.db.async_session_manager() as db:  # type: ignore
            result = await db.execute(
                select(Server).filter(Server.server_name == self.server_name)
            )
            server = result.scalars().first()
            if server:
                server_info = config_data.get("server_info", {})
                settings = config_data.get("settings", {})

                if "installed_version" in server_info:
                    server.installed_version = server_info["installed_version"]
                if "status" in server_info:
                    server.status = server_info["status"]

                if "autoupdate" in settings:
                    server.autoupdate = settings["autoupdate"]
                if "autostart" in settings:
                    server.autostart = settings["autostart"]
                if "target_version" in settings:
                    server.target_version = settings["target_version"]

                if "custom" in config_data:
                    server.custom = config_data["custom"]
                await db.commit()

    async def _manage_json_config(
        self,
        key: str,
        operation: str,
        value: Any = None,
    ) -> Optional[Any]:
        """Centralized helper to read/write to the server's JSON config asynchronously."""
        if not key:
            raise MissingArgumentError("Config key cannot be empty.")
        operation_lower = str(operation).lower()
        if operation_lower not in ["read", "write"]:
            raise UserInputError(
                f"Invalid operation: '{operation}'. Must be 'read' or 'write'."
            )

        current_config = await self._load_server_config()

        if operation_lower == "read":
            d = current_config
            try:
                for k_part in key.split("."):
                    if not isinstance(d, dict):
                        self.logger.debug(
                            f"Server Config Read: Key='{key}', part '{k_part}' is not a dictionary. Path invalid."
                        )
                        return None
                    d = d[k_part]
                self.logger.debug(
                    f"Server Config Read: Key='{key}', Value='{d}' for '{self.server_name}'"
                )
                return d
            except KeyError:
                self.logger.debug(
                    f"Server Config Read: Key='{key}' not found for '{self.server_name}'. Returning None."
                )
                return None
            except TypeError:
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
        for k_part in keys_list[:-1]:
            if not isinstance(d, dict):
                raise ConfigParseError(
                    f"Cannot create nested key '{key}': part '{k_part}' conflicts with existing non-dictionary value in config for '{self.server_name}'."
                )
            d = d.setdefault(k_part, {})
            if not isinstance(d, dict):
                raise ConfigParseError(
                    f"Cannot create nested key '{key}': part '{k_part}' resulted in a non-dictionary in config for '{self.server_name}'."
                )

        if not isinstance(d, dict):
            raise ConfigParseError(
                f"Cannot set key '{keys_list[-1]}' in path '{'.'.join(keys_list[:-1])}': parent is not a dictionary in config for '{self.server_name}'."
            )
        d[keys_list[-1]] = value

        await self._save_server_config(current_config)
        return None

    async def get_version(self) -> str:
        """Retrieves the 'installed_version' from the server's config asynchronously.

        Accesses ``server_info.installed_version`` via :meth:`._async_manage_json_config`.

        Returns:
            str: The installed version string, or "UNKNOWN" if not set or on error.
        """
        self.logger.debug(
            f"Getting installed version for server '{self.server_name}' asynchronously."
        )
        try:
            version = await self._manage_json_config(
                key="server_info.installed_version", operation="read"
            )
            return str(version) if version is not None else "UNKNOWN"
        except Exception as e:
            self.logger.error(
                f"Error getting version for '{self.server_name}': {e}", exc_info=True
            )
            return "UNKNOWN"

    async def set_version(self, version_string: str) -> None:
        """Sets the 'installed_version' in the server's config asynchronously.

        Updates ``server_info.installed_version`` via :meth:`._async_manage_json_config`.

        Args:
            version_string (str): The version string to set (e.g., "1.20.30.02").

        Raises:
            UserInputError: If `version_string` is not a string.
        """
        self.logger.debug(
            f"Setting installed version for '{self.server_name}' to '{version_string}' asynchronously."
        )
        if not isinstance(version_string, str):
            raise UserInputError(
                f"Version for '{self.server_name}' must be a string, got {type(version_string).__name__}."
            )
        await self._manage_json_config(
            key="server_info.installed_version", operation="write", value=version_string
        )
        self.logger.info(f"Version for '{self.server_name}' set to '{version_string}'.")

    async def get_autoupdate(self) -> bool:
        """Retrieves the 'autoupdate' setting from the server's config asynchronously.

        Accesses ``settings.autoupdate`` via :meth:`._async_manage_json_config`.

        Returns:
            bool: The autoupdate status (``True`` or ``False``). Defaults to ``False``
            if the setting is not found or an error occurs during retrieval.
        """
        self.logger.debug(
            f"Getting autoupdate value for server '{self.server_name}' asynchronously."
        )
        try:
            autoupdate_setting = await self._manage_json_config(
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

    async def set_autoupdate(self, value: bool) -> None:
        """Sets the 'autoupdate' setting in the server's config asynchronously.

        Updates ``settings.autoupdate`` via :meth:`._async_manage_json_config`.

        Args:
            value (bool): The boolean value to set for autoupdate.

        Raises:
            UserInputError: If `value` is not a boolean.
        """
        self.logger.debug(
            f"Setting autoupdate for '{self.server_name}' to '{value}' asynchronously."
        )
        if not isinstance(value, bool):
            raise UserInputError(
                f"Autoupdate value for '{self.server_name}' must be a boolean, got {type(value).__name__}."
            )
        await self._manage_json_config(
            key="settings.autoupdate", operation="write", value=value
        )
        self.logger.info(f"Autoupdate for '{self.server_name}' set to '{value}'.")

    async def get_autostart(self) -> bool:
        """Retrieves the 'autostart' setting from the server's config asynchronously.

        Accesses ``settings.autostart`` via :meth:`._async_manage_json_config`.

        Returns:
            bool: The autostart status (``True`` or ``False``). Defaults to ``False``
            if the setting is not found or an error occurs during retrieval.
        """
        self.logger.debug(
            f"Getting autostart value for server '{self.server_name}' asynchronously."
        )
        try:
            autostart_setting = await self._manage_json_config(
                key="settings.autostart", operation="read"
            )
            if isinstance(autostart_setting, bool):
                return autostart_setting
            # Handle string "true"/"false" for robustness if manually edited or from old versions
            if isinstance(autostart_setting, str):
                return autostart_setting.lower() == "true"
            self.logger.warning(
                f"autostart setting for '{self.server_name}' is not a boolean, found: {autostart_setting}. Defaulting to False."
            )
            return False  # Default if not found or invalid type
        except Exception as e:
            self.logger.error(
                f"Error getting autostart setting for '{self.server_name}': {e}. Defaulting to False.",
                exc_info=True,
            )
            return False

    async def set_autostart(self, value: bool) -> None:
        """Sets the 'autostart' setting in the server's config asynchronously.

        Updates ``settings.autostart`` via :meth:`._async_manage_json_config`.

        Args:
            value (bool): The boolean value to set for autostart.

        Raises:
            UserInputError: If `value` is not a boolean.
        """
        self.logger.debug(
            f"Setting autostart for '{self.server_name}' to '{value}' asynchronously."
        )
        if not isinstance(value, bool):
            raise UserInputError(
                f"autostart value for '{self.server_name}' must be a boolean, got {type(value).__name__}."
            )
        await self._manage_json_config(
            key="settings.autostart", operation="write", value=value
        )
        self.logger.info(f"autostart for '{self.server_name}' set to '{value}'.")

    async def get_status_from_config(self) -> str:
        """Retrieves the stored 'status' from the server's config asynchronously.

        Accesses ``server_info.status`` via :meth:`._async_manage_json_config`. This
        reflects the last known status written to the config, not necessarily
        the live process status. For live status, use :meth:`.get_status`.

        Returns:
            str: The stored status string (e.g., "RUNNING", "STOPPED"), or
            "UNKNOWN" if not set or on error.
        """
        self.logger.debug(
            f"Getting stored status for '{self.server_name}' from JSON config asynchronously."
        )
        try:
            status = await self._manage_json_config(
                key="server_info.status", operation="read"
            )
            return str(status) if status is not None else "UNKNOWN"
        except Exception as e:
            self.logger.error(
                f"Error getting status from JSON config for '{self.server_name}': {e}",
                exc_info=True,
            )
            return "UNKNOWN"

    async def set_status_in_config(self, status_string: str) -> None:
        """Sets the 'status' in the server's config asynchronously.

        Updates ``server_info.status`` via :meth:`._async_manage_json_config`. This is
        used to persist the server's state.

        Args:
            status_string (str): The status string to set (e.g., "RUNNING", "STOPPED").

        Raises:
            UserInputError: If `status_string` is not a string.
        """
        self.logger.debug(
            f"Setting status in JSON config for '{self.server_name}' to '{status_string}' asynchronously."
        )
        if not isinstance(status_string, str):
            raise UserInputError(
                f"Status for '{self.server_name}' must be a string, got {type(status_string).__name__}."
            )

        try:
            await self.app_context.api.set_server_status_api(
                self.server_name, status_string
            )
            return
        except AttributeError:
            pass

        await self._manage_json_config(
            key="server_info.status", operation="write", value=status_string
        )
        self.logger.info(
            f"Status in JSON config for '{self.server_name}' set to '{status_string}'."
        )

    async def get_target_version(self) -> str:
        """Retrieves the 'target_version' from the server's config asynchronously.

        Accesses ``settings.target_version`` via
        :meth:`._async_manage_json_config`. This indicates the version the server aims
        to be on, often "LATEST" or a specific version string.

        Returns:
            str: The target version string, or "LATEST" if not set or on error.
        """
        self.logger.debug(
            f"Getting stored target_version for '{self.server_name}' from JSON config asynchronously."
        )
        try:
            version = await self._manage_json_config(
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

    async def set_target_version(self, version_string: str) -> None:
        """Sets the 'target_version' in the server's config asynchronously.

        Updates ``settings.target_version`` via
        :meth:`._async_manage_json_config`.

        Args:
            version_string (str): The target version string to set (e.g., "LATEST", "1.20.30.02").

        Raises:
            UserInputError: If `version_string` is not a string.
        """
        self.logger.debug(
            f"Setting target_version for '{self.server_name}' to '{version_string}' asynchronously."
        )
        if not isinstance(version_string, str):
            raise UserInputError(
                f"target_version for '{self.server_name}' must be a string, got {type(version_string).__name__}."
            )
        await self._manage_json_config(
            key="settings.target_version", operation="write", value=version_string
        )
        self.logger.info(
            f"target_version for '{self.server_name}' set to '{version_string}'."
        )

    async def get_custom_config_value(self, key: str) -> Optional[Any]:
        """Retrieves a custom value from the 'custom' section of the server's config asynchronously.

        Accesses ``custom.<key>`` via :meth:`._async_manage_json_config`.

        Args:
            key (str): The key of the custom value to retrieve.

        Returns:
            Optional[Any]: The retrieved custom value, or ``None`` if the key
            is not found or an error occurs.

        Raises:
            UserInputError: If `key` is not a non-empty string.
        """
        self.logger.debug(
            f"Getting custom config key '{key}' for server '{self.server_name}' asynchronously."
        )
        if not isinstance(key, str) or not key:
            raise UserInputError(
                f"Key for custom config on '{self.server_name}' must be a non-empty string."
            )
        full_key = f"custom.{key}"
        value = await self._manage_json_config(key=full_key, operation="read")
        self.logger.debug(
            f"Retrieved custom config for '{self.server_name}': Key='{key}', Value='{value}'."
        )
        return value

    async def set_custom_config_value(self, key: str, value: Any) -> None:
        """Sets a custom key-value pair in the 'custom' section of the server's config asynchronously.

        Updates ``custom.<key>`` via :meth:`._async_manage_json_config`.

        Args:
            key (str): The key for the custom value.
            value (Any): The value to set. Must be JSON serializable.

        Raises:
            UserInputError: If `key` is not a non-empty string.
            ConfigParseError: If `value` is not JSON serializable (from underlying save).
        """
        self.logger.debug(
            f"Setting custom config for '{self.server_name}': Key='{key}', Value='{value}' asynchronously."
        )
        if not isinstance(key, str) or not key:
            raise UserInputError(
                f"Key for custom config on '{self.server_name}' must be a non-empty string."
            )
        full_key = f"custom.{key}"
        await self._manage_json_config(key=full_key, operation="write", value=value)
        self.logger.info(
            f"Custom config for '{self.server_name}' set: Key='{key}', Value='{value}'."
        )

    async def get_world_name(self) -> str:
        """Reads the ``level-name`` property from the server's ``server.properties`` file asynchronously.

        Returns:
            str: The name of the world as specified in ``server.properties``.

        Raises:
            AppFileNotFoundError: If the ``server.properties`` file does not exist
                at the expected path (:attr:`.server_properties_path`).
            ConfigParseError: If the file cannot be read (e.g., due to permissions)
                or if the ``level-name`` key is missing, malformed, or has an empty value.
        """
        from ...utils.io import async_load_lines

        self.logger.debug(
            f"Reading world name for server '{self.server_name}' from: {self.server_properties_path} asynchronously"
        )
        if not await aiofiles.ospath.isfile(self.server_properties_path):
            raise AppFileNotFoundError(
                self.server_properties_path, "server.properties file"
            )

        try:
            lines = await async_load_lines(self.server_properties_path)
            for line_content in lines:
                line = line_content.strip()
                if line.startswith("level-name="):
                    parts = line.split("=", 1)
                    if len(parts) == 2 and parts[1].strip():
                        world_name = parts[1].strip()
                        self.logger.debug(
                            f"Found world name (level-name): '{world_name}' for '{self.server_name}'"
                        )
                        return world_name
                    else:
                        raise ConfigParseError(
                            f"'level-name' property malformed or has empty value in {self.server_properties_path}"
                        )
        except OSError as e_os:
            raise ConfigParseError(
                f"Failed to read server.properties for '{self.server_name}': {e_os}"
            ) from e_os

        raise ConfigParseError(
            f"'level-name' property not found in {self.server_properties_path}"
        )

    async def get_status(self) -> str:
        """Determines and returns the current reconciled operational status of the server asynchronously.

        This method attempts to determine if the server process is actually running
        (by calling ``self.is_running()``, which is expected to be provided by
        another mixin like ``ProcessMixin``). It then compares this live status
        with the status stored in the server's configuration
        (retrieved via :meth:`.get_status_from_config`).

        If a discrepancy is found (e.g., process is running but config says "STOPPED",
        or vice-versa when config said "RUNNING"), it updates the stored status in
        the config to reflect the actual state.

        Returns:
            str: The reconciled operational status of the server as a string
            (e.g., "RUNNING", "STOPPED"). If ``self.is_running()`` is not available
            or fails, it falls back to returning the last known status from config.
        """
        self.logger.debug(
            f"Determining overall status for server '{self.server_name}' asynchronously."
        )

        actual_is_running = False
        try:
            actual_is_running = await self.is_running()  # type: ignore
        except Exception as e_is_running_check:
            self.logger.error(
                f"Error calling self.is_running() for '{self.server_name}': {e_is_running_check}. Fallback to stored status."
            )
            return await self.get_status_from_config()

        stored_status = await self.get_status_from_config()
        final_status = "UNKNOWN"

        if actual_is_running:
            final_status = "RUNNING"
            if stored_status != "RUNNING":
                self.logger.info(
                    f"Server '{self.server_name}' is running. Updating stored status from '{stored_status}' to RUNNING."
                )
                try:
                    await self.set_status_in_config("RUNNING")
                except Exception as e_set_cfg:
                    self.logger.warning(
                        f"Failed to update stored status to RUNNING for '{self.server_name}': {e_set_cfg}"
                    )
        else:
            if stored_status == "RUNNING":
                self.logger.info(
                    f"Server '{self.server_name}' not running but stored status was RUNNING. Updating to STOPPED."
                )
                final_status = "STOPPED"
                try:
                    await self.set_status_in_config("STOPPED")
                except Exception as e_set_cfg:
                    self.logger.warning(
                        f"Failed to update stored status to STOPPED for '{self.server_name}': {e_set_cfg}"
                    )
            elif stored_status == "UNKNOWN":
                final_status = "STOPPED"
            else:
                final_status = stored_status

        self.logger.debug(
            f"Final determined status for '{self.server_name}': {final_status}"
        )
        return final_status
