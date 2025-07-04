# bedrock_server_manager/core/manager.py
"""
Defines the :class:`~.BedrockServerManager`, the application's central orchestrator.

This module provides the :class:`~.BedrockServerManager` class, which serves as
the primary high-level interface for managing application-wide aspects of the
Bedrock Server Manager. Unlike the :class:`~.core.bedrock_server.BedrockServer`
class that manages individual server instances, the :class:`~.BedrockServerManager`
handles operations that span across multiple servers or pertain to the application
as a whole.

Key responsibilities include:

    - Accessing and managing global application settings via the :class:`~.config.settings.Settings` object.
    - Discovering and validating existing Bedrock server installations.
    - Managing a central player database (``players.json``) by aggregating player
      information from individual server logs.
    - Controlling the lifecycle of the Web UI application, including its system service
      (Systemd on Linux, Windows Service on Windows).
    - Listing globally available content, such as ``.mcworld`` and addon files.
    - Checking and reporting system capabilities relevant to the application's features.

"""
import os
import json
import shutil
import glob
import logging
import platform
import subprocess
from typing import Optional, List, Dict, Any, Union, Tuple

# Local application imports.
from bedrock_server_manager.config.settings import Settings
from bedrock_server_manager.core.bedrock_server import BedrockServer
from bedrock_server_manager.config.const import EXPATH, app_name_title, package_name
from bedrock_server_manager.error import (
    ConfigurationError,
    FileOperationError,
    UserInputError,
    SystemError,
    CommandNotFoundError,
    PermissionsError,
    AppFileNotFoundError,
    InvalidServerNameError,
    MissingArgumentError,
)

if platform.system() == "Linux":
    from bedrock_server_manager.core.system import linux as system_linux_utils
elif platform.system() == "Windows":
    from bedrock_server_manager.core.system import windows as system_windows_utils

logger = logging.getLogger(__name__)


class BedrockServerManager:
    """
    Manages global application settings, server discovery, and application-wide data.

    The :class:`~.BedrockServerManager` serves as the primary high-level interface
    for operations that affect the Bedrock Server Manager application globally or
    span multiple server instances. It is distinct from the
    :class:`~.core.bedrock_server.BedrockServer` class, which handles the specifics
    of individual server instances.

    Key Responsibilities:

        - Providing access to and management of global application settings through
          an aggregated :class:`~.config.settings.Settings` object.
        - Discovering server instances within the configured base directory and
          validating their installations.
        - Managing a central player database (``players.json``), including parsing
          player data and consolidating information from server logs.
        - Controlling the Web UI application's lifecycle, including managing its
          system service (Systemd for Linux, Windows Service for Windows).
        - Listing globally available content files (e.g., ``.mcworld`` templates,
          ``.mcaddon``/``.mcpack`` addons) from the content directory.
        - Checking and reporting on system capabilities (e.g., availability of
          task schedulers or service managers).

    An instance of this class is typically created once per application run. It
    initializes by loading or accepting a :class:`~.config.settings.Settings`
    instance and sets up paths based on this configuration. For operations that
    require interaction with a specific server (like scanning its logs), it will
    internally instantiate a :class:`~.core.bedrock_server.BedrockServer` object.

    Attributes:
        settings (:class:`~.config.settings.Settings`): The application's global
            settings object.
        capabilities (Dict[str, bool]): A dictionary indicating the availability
            of system features like 'scheduler' and 'service_manager'.
        _config_dir (str): Absolute path to the application's configuration directory.
        _app_data_dir (str): Absolute path to the application's data directory.
        _base_dir (Optional[str]): Absolute path to the base directory where server
            installations are stored. Based on ``settings['paths.servers']``.
        _content_dir (Optional[str]): Absolute path to the directory for global
            content like world templates and addons. Based on ``settings['paths.content']``.
        _expath (str): Path to the main BSM executable/script.
        _app_version (str): The application's version string.
        _WEB_SERVER_PID_FILENAME (str): Filename for the Web UI PID file.
        _WEB_SERVICE_SYSTEMD_NAME (str): Name for the Web UI systemd service.
        _WEB_SERVICE_WINDOWS_NAME_INTERNAL (str): Internal name for the Web UI Windows service.
        _WEB_SERVICE_WINDOWS_DISPLAY_NAME (str): Display name for the Web UI Windows service.
    """

    def __init__(self, settings_instance: Optional[Settings] = None) -> None:
        """
        Initializes the BedrockServerManager instance.

        This constructor sets up the manager by:

            1. Initializing or accepting an instance of the :class:`~.config.settings.Settings`
               class, which provides access to all application configurations.
            2. Performing a check for system capabilities (e.g., availability of
               ``crontab``, ``systemctl``) via :meth:`._check_system_capabilities`
               and logging warnings for missing dependencies via :meth:`._log_capability_warnings`.
            3. Caching essential paths (configuration directory, application data directory,
               servers base directory, content directory) and constants from the settings
               and application constants.
            4. Defining constants for Web UI process/service management (PID filename,
               service names for Systemd and Windows).
            5. Validating that critical directory paths (servers base directory, content
               directory) are configured in settings, raising a
               :class:`~.error.ConfigurationError` if not.

        Args:
            settings_instance (Optional[:class:`~.config.settings.Settings`]):
                An optional, pre-configured :class:`~.config.settings.Settings`
                object. If ``None`` (default), a new :class:`~.config.settings.Settings`
                object will be instantiated and loaded. This parameter allows for
                dependency injection, primarily for testing purposes.

        Raises:
            ConfigurationError: If the provided or loaded :class:`~.config.settings.Settings`
                object is misconfigured (e.g., missing critical path definitions like
                ``paths.servers`` or ``paths.content``), or if core application
                constants cannot be accessed.
        """
        if settings_instance:
            self.settings = settings_instance
        else:
            self.settings = Settings()
        logger.debug(
            f"BedrockServerManager initialized using settings from: {self.settings.config_path}"
        )

        self.capabilities = self._check_system_capabilities()
        self._log_capability_warnings()

        # Initialize core attributes from the settings object.
        try:
            self._config_dir = self.settings.config_dir
            self._app_data_dir = self.settings.app_data_dir
            self._app_name_title = app_name_title
            self._package_name = package_name
            self._expath = str(EXPATH)
        except Exception as e:
            raise ConfigurationError(f"Settings object is misconfigured: {e}") from e

        self._base_dir = self.settings.get("paths.servers")
        self._content_dir = self.settings.get("paths.content")

        # Constants for managing the web server process.
        self._WEB_SERVER_PID_FILENAME = "web_server.pid"
        self._WEB_SERVER_START_ARG = ["web", "start"]

        _clean_package_name_for_systemd = (
            self._package_name.lower().replace("_", "-").replace(" ", "-")
        )
        self._WEB_SERVICE_SYSTEMD_NAME = (
            f"{_clean_package_name_for_systemd}-webui.service"
        )

        # Ensure app_name_title is suitable for Windows service name
        _clean_app_title_for_windows = "".join(
            c for c in self._app_name_title if c.isalnum()
        )
        if (
            not _clean_app_title_for_windows
        ):  # Fallback if app_name_title was all special chars
            _clean_app_title_for_windows = "AppWebUI"  # Generic fallback
        self._WEB_SERVICE_WINDOWS_NAME_INTERNAL = f"{_clean_app_title_for_windows}WebUI"
        self._WEB_SERVICE_WINDOWS_DISPLAY_NAME = f"{self._app_name_title} Web UI"

        try:
            self._app_version = self.settings.version
        except Exception:
            self._app_version = "0.0.0"

        # Validate that essential directory settings are present.
        if not self._base_dir:
            raise ConfigurationError("BASE_DIR not configured in settings.")
        if not self._content_dir:
            raise ConfigurationError("CONTENT_DIR not configured in settings.")

    # --- Settings Related ---
    def get_setting(self, key: str, default: Any = None) -> Any:
        """Retrieves a configuration value by its key from the global settings.

        This method acts as a proxy to the :meth:`~.config.settings.Settings.get`
        method of the underlying :class:`~.config.settings.Settings` object.

        Args:
            key (str): The dot-separated key of the setting to retrieve
                (e.g., ``"web.port"``, ``"paths.servers"``).
            default (Any): The value to return if the key is not found.
                Defaults to ``None``.

        Returns:
            Any: The value of the setting, or the ``default`` value if the key
            is not found. The actual type depends on the setting being retrieved.
        """
        return self.settings.get(key, default)

    def set_setting(self, key: str, value: Any) -> None:
        """Sets a configuration value by its key in the global settings and saves it.

        This method acts as a proxy to the :meth:`~.config.settings.Settings.set`
        method of the underlying :class:`~.config.settings.Settings` object.
        Changes made through this method are typically persisted to the
        application's configuration file.

        Args:
            key (str): The dot-separated key of the setting to set
                (e.g., ``"web.port"``, ``"logging.level"``).
            value (Any): The new value for the setting.

        Raises:
            Various (from :class:`~.config.settings.Settings`): Potentially
                :class:`~.error.FileOperationError` if saving the settings file fails.
        """
        self.settings.set(key, value)

    # --- Player Database Management ---
    def _get_player_db_path(self) -> str:
        """Returns the absolute path to the central ``players.json`` file.

        The path is constructed by joining the application's configuration directory
        (:attr:`._config_dir`) with the filename "players.json".

        Returns:
            str: The absolute path to where the ``players.json`` file is expected to be.
        """
        return os.path.join(self._config_dir, "players.json")

    def parse_player_cli_argument(self, player_string: str) -> List[Dict[str, str]]:
        """Parses a comma-separated string of 'player_name:xuid' pairs.

        This utility method is designed to process player data provided as a
        single string, typically from a command-line argument. Each player entry
        in the string should be in the format "PlayerName:PlayerXUID", and multiple
        entries should be separated by commas. Whitespace around names, XUIDs,
        commas, and colons is generally handled.

        Example:
            ``"Player One:12345, PlayerTwo:67890"``

        Args:
            player_string (str): The comma-separated string of player data.
                If empty or not a string, an empty list is returned.

        Returns:
            List[Dict[str, str]]: A list of dictionaries. Each dictionary
            represents a player and contains two keys:

                - ``"name"`` (str): The player's name.
                - ``"xuid"`` (str): The player's XUID.

            Returns an empty list if the input ``player_string`` is empty or invalid.

        Raises:
            UserInputError: If any player pair within the string does not conform
                to the "name:xuid" format, or if a name or XUID is empty after stripping.
        """
        if not player_string or not isinstance(player_string, str):
            return []
        logger.debug(f"BSM: Parsing player argument string: '{player_string}'")
        player_list: List[Dict[str, str]] = []
        player_pairs = [
            pair.strip() for pair in player_string.split(",") if pair.strip()
        ]
        for pair in player_pairs:
            player_data = pair.split(":", 1)
            if len(player_data) != 2:
                raise UserInputError(
                    f"Invalid player data format: '{pair}'. Expected 'name:xuid'."
                )
            player_name, player_id = player_data[0].strip(), player_data[1].strip()
            if not player_name or not player_id:
                raise UserInputError(f"Name and XUID cannot be empty in '{pair}'.")
            player_list.append({"name": player_name.strip(), "xuid": player_id.strip()})
        return player_list

    def save_player_data(self, players_data: List[Dict[str, str]]) -> int:
        """Saves or updates player data in the central ``players.json`` file.

        This method merges the provided ``players_data`` with any existing player
        data in the ``players.json`` file located in the application's configuration
        directory (see :meth:`._get_player_db_path`).

        The merging logic is as follows:

            - If a player's XUID from ``players_data`` already exists in the database,
              their entry (name and XUID) is updated if different.
            - If a player's XUID is new, their entry is added to the database.

        The final list of players is sorted alphabetically by name before being
        written to the file. The configuration directory is created if it doesn't exist.

        Args:
            players_data (List[Dict[str, str]]): A list of player dictionaries.
                Each dictionary must contain string values for ``"name"`` and ``"xuid"`` keys.
                Both name and XUID must be non-empty.

        Returns:
            int: The total number of players that were newly added or had their
            existing entry updated. Returns 0 if no changes were made.

        Raises:
            UserInputError: If ``players_data`` is not a list, or if any dictionary
                within it does not conform to the required format (missing keys,
                non-string values, or empty name/XUID).
            FileOperationError: If creating the configuration directory fails or
                if writing to the ``players.json`` file fails (e.g., due to
                permission issues).
        """
        if not isinstance(players_data, list):
            raise UserInputError("players_data must be a list.")
        for p_data in players_data:
            if not (
                isinstance(p_data, dict)
                and "name" in p_data
                and "xuid" in p_data
                and isinstance(p_data["name"], str)
                and p_data["name"]
                and isinstance(p_data["xuid"], str)
                and p_data["xuid"]
            ):
                raise UserInputError(f"Invalid player entry format: {p_data}")

        player_db_path = self._get_player_db_path()
        try:
            os.makedirs(self._config_dir, exist_ok=True)
        except OSError as e:
            raise FileOperationError(
                f"Could not create config directory {self._config_dir}: {e}"
            ) from e

        # Load existing player data into a map for efficient lookup.
        existing_players_map: Dict[str, Dict[str, str]] = {}
        if os.path.exists(player_db_path):
            try:
                with open(player_db_path, "r", encoding="utf-8") as f:
                    loaded_json = json.load(f)
                    if (
                        isinstance(loaded_json, dict)
                        and "players" in loaded_json
                        and isinstance(loaded_json["players"], list)
                    ):
                        for p_entry in loaded_json["players"]:
                            if isinstance(p_entry, dict) and "xuid" in p_entry:
                                existing_players_map[p_entry["xuid"]] = p_entry
            except (ValueError, OSError) as e:
                logger.warning(
                    f"BSM: Could not load/parse existing players.json, will overwrite: {e}"
                )

        updated_count = 0
        added_count = 0
        # Merge new data with existing data.
        for player_to_add in players_data:
            xuid = player_to_add["xuid"]
            if xuid in existing_players_map:
                if existing_players_map[xuid] != player_to_add:
                    existing_players_map[xuid] = player_to_add
                    updated_count += 1
            else:
                existing_players_map[xuid] = player_to_add
                added_count += 1

        if updated_count > 0 or added_count > 0:
            # Sort the final list alphabetically by name before saving.
            updated_players_list = sorted(
                list(existing_players_map.values()),
                key=lambda p: p.get("name", "").lower(),
            )
            try:
                with open(player_db_path, "w", encoding="utf-8") as f:
                    json.dump({"players": updated_players_list}, f, indent=4)
                logger.info(
                    f"BSM: Saved/Updated players. Added: {added_count}, Updated: {updated_count}. Total in DB: {len(updated_players_list)}"
                )
                return added_count + updated_count
            except OSError as e:
                raise FileOperationError(f"Failed to write players.json: {e}") from e

        logger.debug("BSM: No new or updated player data to save.")
        return 0

    def get_known_players(self) -> List[Dict[str, str]]:
        """Retrieves all known players from the central ``players.json`` file.

        This method reads the ``players.json`` file from the application's
        configuration directory (obtained via :meth:`._get_player_db_path`).
        It expects the file to contain a JSON object with a "players" key,
        which holds a list of player dictionaries.

        Args:
            None

        Returns:
            List[Dict[str, str]]: A list of player dictionaries, where each
            dictionary typically contains ``"name"`` and ``"xuid"`` keys.
            Returns an empty list if the ``players.json`` file does not exist,
            is empty, contains invalid JSON, or does not have the expected
            structure (e.g., missing "players" list). Errors during reading or
            parsing are logged.
        """
        player_db_path = self._get_player_db_path()
        if not os.path.exists(player_db_path):
            return []
        try:
            with open(player_db_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    return []
                data = json.loads(content)
                if (
                    isinstance(data, dict)
                    and "players" in data
                    and isinstance(data["players"], list)
                ):
                    return data["players"]
                logger.warning(
                    f"BSM: Player DB {player_db_path} has unexpected format."
                )
        except (ValueError, OSError) as e:
            logger.error(f"BSM: Error reading player DB {player_db_path}: {e}")
        return []

    def discover_and_store_players_from_all_server_logs(self) -> Dict[str, Any]:
        """Scans all server logs for player data and updates the central player database.

        This comprehensive method performs the following actions:

            1. Iterates through all subdirectories within the application's base server
               directory (defined by ``settings['paths.servers']``).
            2. For each subdirectory, it attempts to instantiate a
               :class:`~.core.bedrock_server.BedrockServer` object.
            3. If the server instance is valid and installed, it calls the server's
               :meth:`~.core.server.player_mixin.ServerPlayerMixin.scan_log_for_players`
               method to extract player names and XUIDs from its logs.
            4. All player data discovered from all server logs is aggregated.
            5. Unique player entries (based on XUID) are then saved to the central
               ``players.json`` file using :meth:`.save_player_data`.

        Args:
            None

        Returns:
            Dict[str, Any]: A dictionary summarizing the discovery and saving operation,
            containing the following keys:

                - ``"total_entries_in_logs"`` (int): The total number of player entries
                  (possibly non-unique) found across all server logs.
                - ``"unique_players_submitted_for_saving"`` (int): The number of unique
                  player entries (by XUID) that were attempted to be saved.
                - ``"actually_saved_or_updated_in_db"`` (int): The number of players
                  that were newly added or updated in the central ``players.json``
                  by the :meth:`.save_player_data` call.
                - ``"scan_errors"`` (List[Dict[str, str]]): A list of dictionaries,
                  where each entry represents an error encountered while scanning a
                  specific server's logs or saving the global player DB. Each error
                  dictionary contains ``"server"`` (str, server name or "GLOBAL_PLAYER_DB")
                  and ``"error"`` (str, error message).

        Raises:
            AppFileNotFoundError: If the main server base directory
                (``settings['paths.servers']``) is not configured or does not exist.
            FileOperationError: If the final save operation to the central
                ``players.json`` (via :meth:`.save_player_data`) fails due to I/O issues.
                Note that errors during individual server log scans are caught and
                reported in the ``"scan_errors"`` part of the return value.
        """
        if not self._base_dir or not os.path.isdir(self._base_dir):
            raise AppFileNotFoundError(str(self._base_dir), "Server base directory")

        all_discovered_from_logs: List[Dict[str, str]] = []
        scan_errors_details: List[Dict[str, str]] = []

        logger.info(
            f"BSM: Starting discovery of players from all server logs in '{self._base_dir}'."
        )

        for server_name_candidate in os.listdir(self._base_dir):
            potential_server_path = os.path.join(self._base_dir, server_name_candidate)
            if not os.path.isdir(potential_server_path):
                continue

            logger.debug(f"BSM: Processing potential server '{server_name_candidate}'.")
            try:
                # Instantiate a BedrockServer to use its encapsulated logic.
                server_instance = BedrockServer(
                    server_name=server_name_candidate,
                    settings_instance=self.settings,
                    manager_expath=self._expath,
                )

                # Validate it's a real server before trying to scan its logs.
                if not server_instance.is_installed():
                    logger.debug(
                        f"BSM: '{server_name_candidate}' is not a valid Bedrock server installation. Skipping log scan."
                    )
                    continue

                # Use the instance's own method to scan its log file.
                players_in_log = server_instance.scan_log_for_players()
                if players_in_log:
                    all_discovered_from_logs.extend(players_in_log)
                    logger.debug(
                        f"BSM: Found {len(players_in_log)} players in log for server '{server_name_candidate}'."
                    )

            except FileOperationError as e:
                logger.warning(
                    f"BSM: Error scanning log for server '{server_name_candidate}': {e}"
                )
                scan_errors_details.append(
                    {"server": server_name_candidate, "error": str(e)}
                )
            except Exception as e_instantiate:
                logger.error(
                    f"BSM: Error processing server '{server_name_candidate}' for player discovery: {e_instantiate}",
                    exc_info=True,
                )
                scan_errors_details.append(
                    {
                        "server": server_name_candidate,
                        "error": f"Unexpected error: {str(e_instantiate)}",
                    }
                )

        saved_count = 0
        unique_players_to_save_map = {}
        if all_discovered_from_logs:
            # Consolidate all found players into a unique set by XUID.
            unique_players_to_save_map = {
                p["xuid"]: p for p in all_discovered_from_logs
            }
            unique_players_to_save_list = list(unique_players_to_save_map.values())
            try:
                # Save all unique players to the central database.
                saved_count = self.save_player_data(unique_players_to_save_list)
            except (FileOperationError, Exception) as e_save:
                logger.error(
                    f"BSM: Critical error saving player data to global DB: {e_save}",
                    exc_info=True,
                )
                scan_errors_details.append(
                    {
                        "server": "GLOBAL_PLAYER_DB",
                        "error": f"Save failed: {str(e_save)}",
                    }
                )

        return {
            "total_entries_in_logs": len(all_discovered_from_logs),
            "unique_players_submitted_for_saving": len(unique_players_to_save_map),
            "actually_saved_or_updated_in_db": saved_count,
            "scan_errors": scan_errors_details,
        }

    # --- Web UI Process Management ---
    def start_web_ui_direct(
        self, host: Optional[Union[str, List[str]]] = None, debug: bool = False
    ) -> None:
        """Starts the Web UI application directly in the current process (blocking).

        This method is intended for scenarios where the Web UI is launched with
        the ``--mode direct`` command-line argument. It dynamically imports and
        calls the :func:`~.web.app.run_web_server` function, which in turn
        starts the Uvicorn server hosting the FastAPI application.

        .. note::
            This is a blocking call and will occupy the current process until the
            web server is shut down.

        Args:
            host (Optional[Union[str, List[str]]]): The host address or list of
                addresses for the web server to bind to. Passed directly to
                :func:`~.web.app.run_web_server`. Defaults to ``None``.
            debug (bool): If ``True``, runs the underlying Uvicorn/FastAPI app
                in debug mode (e.g., with auto-reload). Passed directly to
                :func:`~.web.app.run_web_server`. Defaults to ``False``.

        Raises:
            RuntimeError: If :func:`~.web.app.run_web_server` raises a RuntimeError
                (e.g., missing authentication environment variables).
            ImportError: If the web application components (e.g.,
                :func:`~.web.app.run_web_server`) cannot be imported.
            Exception: Re-raises other exceptions from :func:`~.web.app.run_web_server`
                if Uvicorn fails to start.
        """
        logger.info("BSM: Starting web application in direct mode (blocking)...")
        try:
            from bedrock_server_manager.web.app import (
                run_web_server as run_bsm_web_application,
            )

            run_bsm_web_application(host, debug)
            logger.info("BSM: Web application (direct mode) shut down.")
        except (RuntimeError, ImportError) as e:
            logger.critical(
                f"BSM: Failed to start web application directly: {e}", exc_info=True
            )
            raise

    def get_web_ui_pid_path(self) -> str:
        """Returns the absolute path to the PID file for the detached Web UI server.

        The PID file is typically stored in the application's configuration directory
        (:attr:`._config_dir`) with the filename defined by
        :attr:`._WEB_SERVER_PID_FILENAME`.

        Returns:
            str: The absolute path to the Web UI's PID file.
        """
        return os.path.join(self._config_dir, self._WEB_SERVER_PID_FILENAME)

    def get_web_ui_expected_start_arg(self) -> List[str]:
        """Returns the list of arguments used to identify a detached Web UI server process.

        These arguments (defined by :attr:`._WEB_SERVER_START_ARG`) are typically
        used by process management utilities to find and identify the correct
        Web UI server process when it's run in a detached or background mode.

        Returns:
            List[str]: A list of command-line arguments.
        """
        return self._WEB_SERVER_START_ARG

    def get_web_ui_executable_path(self) -> str:
        """Returns the path to the main application executable used for starting the Web UI.

        This path, stored in :attr:`._expath`, is essential for constructing
        commands to start the Web UI, especially for system services.

        Returns:
            str: The path to the application executable.

        Raises:
            ConfigurationError: If the application executable path (:attr:`._expath`)
                is not configured or is empty.
        """
        if not self._expath:
            raise ConfigurationError(
                "Application executable path (_expath) is not configured."
            )
        return self._expath

    def _ensure_linux_for_web_service(self, operation_name: str) -> None:
        """Ensures the current OS is Linux before proceeding with a Web UI systemd operation.

        Args:
            operation_name (str): The name of the operation being attempted,
                used in the error message if the OS is not Linux.

        Raises:
            SystemError: If the current operating system is not Linux.
        """
        if self.get_os_type() != "Linux":
            msg = f"Web UI Systemd operation '{operation_name}' is only supported on Linux. Current OS: {self.get_os_type()}"
            logger.warning(msg)
            raise SystemError(msg)

    def _ensure_windows_for_web_service(self, operation_name: str) -> None:
        """Ensures the current OS is Windows before proceeding with a Web UI service operation.

        Args:
            operation_name (str): The name of the operation being attempted,
                used in the error message if the OS is not Windows.

        Raises:
            SystemError: If the current operating system is not Windows.
        """
        if self.get_os_type() != "Windows":
            msg = f"Web UI Windows Service operation '{operation_name}' is only supported on Windows. Current OS: {self.get_os_type()}"
            logger.warning(msg)
            raise SystemError(msg)

    def _build_web_service_start_command(self) -> str:
        """Builds the command string used to start the Web UI as a service.

        This command typically involves the application executable (:attr:`._expath`)
        followed by arguments to start the web server in "direct" mode.
        The executable path is quoted if it contains spaces.

        Returns:
            str: The fully constructed command string.

        Raises:
            AppFileNotFoundError: If the manager executable path (:attr:`._expath`)
                is not configured or the file does not exist.
        """
        if not self._expath or not os.path.isfile(self._expath):
            raise AppFileNotFoundError(
                str(self._expath), "Manager executable for Web UI service"
            )

        exe_path_to_use = self._expath
        # Quote executable path if it contains spaces and isn't already quoted.
        # This is particularly important for Windows `binPath`.
        if " " in exe_path_to_use and not (
            exe_path_to_use.startswith('"') and exe_path_to_use.endswith('"')
        ):
            exe_path_to_use = f'"{exe_path_to_use}"'

        command_parts = [exe_path_to_use, "web", "start", "--mode", "direct"]

        return " ".join(command_parts)

    def create_web_service_file(self) -> None:
        """Creates or updates the system service file/entry for the Web UI.

        This method handles the OS-specific logic for creating a system service
        that will run the Bedrock Server Manager Web UI.

            - On Linux, it creates a systemd user service file using
              :func:`~.core.system.linux.create_systemd_service_file`.
              The service will be named based on :attr:`._WEB_SERVICE_SYSTEMD_NAME`.
            - On Windows, it creates a new Windows Service using
              :func:`~.core.system.windows.create_windows_service`.
              The service will be named based on :attr:`._WEB_SERVICE_WINDOWS_NAME_INTERNAL`
              and :attr:`._WEB_SERVICE_WINDOWS_DISPLAY_NAME`.

        The start command for the service is constructed by :meth:`._build_web_service_start_command`.
        The application data directory (:attr:`._app_data_dir`) is typically used as the
        working directory for the service.

        Raises:
            SystemError: If the current operating system is not supported (not Linux or Windows),
                or if underlying system utility commands fail during service creation.
            AppFileNotFoundError: If the main manager executable path (:attr:`._expath`)
                is not found or configured.
            FileOperationError: If file or directory operations fail (e.g., creating
                the working directory for the service, or writing the systemd file).
            PermissionsError: On Windows, if the operation is not performed with
                Administrator privileges. On Linux, if user service directories
                are not writable.
            CommandNotFoundError: If essential system commands like ``systemctl`` (Linux)
                or ``sc.exe`` (Windows) are not found in the system's PATH.
            MissingArgumentError: If required internal values for service creation are missing.
        """

        os_type = self.get_os_type()
        start_command = self._build_web_service_start_command()

        if os_type == "Linux":
            self._ensure_linux_for_web_service("create_web_service_file")

            stop_command_exe_path = self._expath
            if " " in stop_command_exe_path and not (
                stop_command_exe_path.startswith('"')
                and stop_command_exe_path.endswith('"')
            ):
                stop_command_exe_path = f'"{stop_command_exe_path}"'
            stop_command = f"{stop_command_exe_path} web stop"  # Generic web stop

            description = f"{self._app_name_title} Web UI Service"
            # Use app_data_dir as working directory; ensure it exists.
            working_dir = self._app_data_dir
            if not os.path.isdir(working_dir):
                try:
                    os.makedirs(working_dir, exist_ok=True)
                    logger.debug(f"Ensured working directory exists: {working_dir}")
                except OSError as e:
                    raise FileOperationError(
                        f"Failed to create working directory {working_dir} for service: {e}"
                    )

            logger.info(
                f"Creating/updating systemd service file '{self._WEB_SERVICE_SYSTEMD_NAME}' for Web UI."
            )
            try:
                system_linux_utils.create_systemd_service_file(
                    service_name_full=self._WEB_SERVICE_SYSTEMD_NAME,
                    description=description,
                    working_directory=working_dir,
                    exec_start_command=start_command,
                    exec_stop_command=stop_command,
                    service_type="simple",  # Web UI is a simple foreground process when in 'direct' mode
                    restart_policy="on-failure",
                    restart_sec=10,
                    after_targets="network.target",  # Ensures network is up
                )
                logger.info(
                    f"Systemd service file for '{self._WEB_SERVICE_SYSTEMD_NAME}' created/updated successfully."
                )
            except (
                MissingArgumentError,
                SystemError,
                CommandNotFoundError,
                AppFileNotFoundError,
                FileOperationError,
            ) as e:
                logger.error(
                    f"Failed to create/update systemd service file for Web UI: {e}"
                )
                raise

        elif os_type == "Windows":
            self._ensure_windows_for_web_service("create_web_service_file")
            description = f"Manages the {self._app_name_title} Web UI."

            if not self._expath or not os.path.isfile(self._expath):
                raise AppFileNotFoundError(
                    str(self._expath), "Manager executable (EXEPATH) for Web UI service"
                )

            # Quote paths and arguments appropriately for the command line.
            quoted_main_exepath = (
                f"{self._expath}"  # The main application executable that has the CLI.
            )

            # Arguments for the `_run-svc` command:
            # 1. The actual service name (this service will register itself with SCM using this name).
            actual_svc_name_arg = f'"{self._WEB_SERVICE_WINDOWS_NAME_INTERNAL}"'

            # Construct the full command for binPath
            windows_service_binpath_command_parts = [
                quoted_main_exepath,
                "service",  # Main command group
                "_run-web",  # The internal service runner command
                actual_svc_name_arg,
            ]

            windows_service_binpath_command = " ".join(
                windows_service_binpath_command_parts
            )

            logger.info(
                f"Creating/updating Windows service '{self._WEB_SERVICE_WINDOWS_NAME_INTERNAL}' for Web UI."
            )
            logger.debug(
                f"Service binPath command will be: {windows_service_binpath_command}"
            )

            try:
                system_windows_utils.create_windows_service(
                    service_name=self._WEB_SERVICE_WINDOWS_NAME_INTERNAL,
                    display_name=self._WEB_SERVICE_WINDOWS_DISPLAY_NAME,
                    description=description,
                    command=windows_service_binpath_command,
                )
                logger.info(
                    f"Windows service '{self._WEB_SERVICE_WINDOWS_NAME_INTERNAL}' created/updated successfully."
                )
            except (
                MissingArgumentError,
                SystemError,
                PermissionsError,
                CommandNotFoundError,
                AppFileNotFoundError,
                FileOperationError,
            ) as e:
                logger.error(f"Failed to create/update Windows service for Web UI: {e}")
                raise
        else:
            raise SystemError(
                f"Web UI service creation is not supported on OS: {os_type}"
            )

    def check_web_service_exists(self) -> bool:
        """Checks if the system service for the Web UI has been created.

        Delegates to OS-specific checks:
        - On Linux, uses :func:`~.core.system.linux.check_service_exists` with :attr:`._WEB_SERVICE_SYSTEMD_NAME`.
        - On Windows, uses :func:`~.core.system.windows.check_service_exists` with :attr:`._WEB_SERVICE_WINDOWS_NAME_INTERNAL`.

        Returns:
            bool: ``True`` if the Web UI service definition exists on the system,
            ``False`` otherwise or if the OS is not supported.
        """
        os_type = self.get_os_type()
        if os_type == "Linux":
            self._ensure_linux_for_web_service("check_web_service_exists")
            return system_linux_utils.check_service_exists(
                self._WEB_SERVICE_SYSTEMD_NAME
            )
        elif os_type == "Windows":
            self._ensure_windows_for_web_service("check_web_service_exists")
            return system_windows_utils.check_service_exists(
                self._WEB_SERVICE_WINDOWS_NAME_INTERNAL
            )
        else:
            logger.debug(f"Web service existence check not supported on OS: {os_type}")
            return False

    def enable_web_service(self) -> None:
        """Enables the Web UI system service to start automatically.

        On Linux, this typically means enabling the systemd service to start on boot or user login.
        Uses :func:`~.core.system.linux.enable_systemd_service`.
        On Windows, this sets the service's start type to "Automatic".
        Uses :func:`~.core.system.windows.enable_windows_service`.

        Raises:
            SystemError: If the OS is not supported or if the underlying
                system command (e.g., ``systemctl``, ``sc.exe``) fails.
            CommandNotFoundError: If system utilities are not found.
            PermissionsError: On Windows, if not run with Administrator privileges.
        """
        os_type = self.get_os_type()
        if os_type == "Linux":
            self._ensure_linux_for_web_service("enable_web_service")
            logger.info(
                f"Enabling systemd service '{self._WEB_SERVICE_SYSTEMD_NAME}' for Web UI."
            )
            system_linux_utils.enable_systemd_service(self._WEB_SERVICE_SYSTEMD_NAME)
            logger.info(f"Systemd service '{self._WEB_SERVICE_SYSTEMD_NAME}' enabled.")
        elif os_type == "Windows":
            self._ensure_windows_for_web_service("enable_web_service")
            logger.info(
                f"Enabling Windows service '{self._WEB_SERVICE_WINDOWS_NAME_INTERNAL}' for Web UI."
            )
            system_windows_utils.enable_windows_service(
                self._WEB_SERVICE_WINDOWS_NAME_INTERNAL
            )
            logger.info(
                f"Windows service '{self._WEB_SERVICE_WINDOWS_NAME_INTERNAL}' enabled."
            )
        else:
            raise SystemError(
                f"Web UI service enabling is not supported on OS: {os_type}"
            )

    def disable_web_service(self) -> None:
        """Disables the Web UI system service from starting automatically.

        On Linux, this typically means disabling the systemd service.
        Uses :func:`~.core.system.linux.disable_systemd_service`.
        On Windows, this sets the service's start type to "Manual" or "Disabled".
        Uses :func:`~.core.system.windows.disable_windows_service`.

        Raises:
            SystemError: If the OS is not supported or if the underlying
                system command fails.
            CommandNotFoundError: If system utilities are not found.
            PermissionsError: On Windows, if not run with Administrator privileges.
        """
        os_type = self.get_os_type()
        if os_type == "Linux":
            self._ensure_linux_for_web_service("disable_web_service")
            logger.info(
                f"Disabling systemd service '{self._WEB_SERVICE_SYSTEMD_NAME}' for Web UI."
            )
            system_linux_utils.disable_systemd_service(self._WEB_SERVICE_SYSTEMD_NAME)
            logger.info(f"Systemd service '{self._WEB_SERVICE_SYSTEMD_NAME}' disabled.")
        elif os_type == "Windows":
            self._ensure_windows_for_web_service("disable_web_service")
            logger.info(
                f"Disabling Windows service '{self._WEB_SERVICE_WINDOWS_NAME_INTERNAL}' for Web UI."
            )
            system_windows_utils.disable_windows_service(
                self._WEB_SERVICE_WINDOWS_NAME_INTERNAL
            )
            logger.info(
                f"Windows service '{self._WEB_SERVICE_WINDOWS_NAME_INTERNAL}' disabled."
            )
        else:
            raise SystemError(
                f"Web UI service disabling is not supported on OS: {os_type}"
            )

    def remove_web_service_file(self) -> bool:
        """Removes the Web UI system service definition.

        .. warning::
            This is a destructive operation. The service should ideally be stopped
            and disabled before removal. After removal, it must be recreated using
            :meth:`.create_web_service_file` if needed again.

        On Linux, this removes the systemd user service file and reloads the systemd daemon.

        Uses :func:`os.remove` and ``systemctl --user daemon-reload``.

        On Windows, this deletes the service using :func:`~.core.system.windows.delete_windows_service`.

        Returns:
            bool
                ``True`` if the service was successfully removed or if it was
                already not found (considered idempotent for removal).

        Raises:
            SystemError
                If the OS is not supported.
            FileOperationError
                On Linux, if removing the service file fails.
            CommandNotFoundError
                If system utilities are not found.
            PermissionsError
                On Windows, if not run with Administrator privileges.

                Details of what "Various" includes, for example, it can include
                    :class:`~.error.SubprocessError` if ``sc.exe delete`` fails.
        """
        os_type = self.get_os_type()
        if os_type == "Linux":
            self._ensure_linux_for_web_service("remove_web_service_file")
            service_file_path = system_linux_utils.get_systemd_user_service_file_path(
                self._WEB_SERVICE_SYSTEMD_NAME
            )
            if os.path.isfile(service_file_path):
                logger.info(f"Removing systemd service file: {service_file_path}")
                try:
                    os.remove(service_file_path)
                    systemctl_cmd = shutil.which("systemctl")
                    if systemctl_cmd:  # Reload daemon if systemctl is available
                        subprocess.run(
                            [systemctl_cmd, "--user", "daemon-reload"],
                            check=False,
                            capture_output=True,
                        )
                    logger.info(
                        f"Removed systemd service file for Web UI '{self._WEB_SERVICE_SYSTEMD_NAME}' and reloaded daemon."
                    )
                    return True
                except OSError as e:
                    raise FileOperationError(
                        f"Failed to remove systemd service file for Web UI: {e}"
                    ) from e
            else:
                logger.debug(
                    f"Systemd service file for Web UI '{self._WEB_SERVICE_SYSTEMD_NAME}' not found. No removal needed."
                )
                return (
                    True  # Consistent with original mixin: true if not found or removed
                )
        elif os_type == "Windows":
            self._ensure_windows_for_web_service("remove_web_service_file")
            logger.info(
                f"Removing Windows service '{self._WEB_SERVICE_WINDOWS_NAME_INTERNAL}' for Web UI."
            )
            system_windows_utils.delete_windows_service(
                self._WEB_SERVICE_WINDOWS_NAME_INTERNAL
            )  # This should handle if not exists gracefully or raise
            logger.info(
                f"Windows service '{self._WEB_SERVICE_WINDOWS_NAME_INTERNAL}' removed (if it existed)."
            )
            return True  # Assuming delete_windows_service is idempotent or handles "not found"
        else:
            raise SystemError(
                f"Web UI service removal is not supported on OS: {os_type}"
            )

    def is_web_service_active(self) -> bool:
        """Checks if the Web UI system service is currently active (running).

        Delegates to OS-specific checks:

            - On Linux, uses ``systemctl --user is-active`` for the service named
              by :attr:`._WEB_SERVICE_SYSTEMD_NAME`.
            - On Windows, uses ``sc query`` for the service named by
              :attr:`._WEB_SERVICE_WINDOWS_NAME_INTERNAL`.

        Returns ``False`` if the OS is not supported, if system utilities
        (``systemctl``, ``sc.exe``) are not found, or if the service is not active.
        Errors during the check are logged.

        Returns:
            bool: ``True`` if the Web UI service is determined to be active,
            ``False`` otherwise.
        """
        os_type = self.get_os_type()
        if os_type == "Linux":
            self._ensure_linux_for_web_service("is_web_service_active")
            systemctl_cmd = shutil.which("systemctl")
            if not systemctl_cmd:
                logger.warning(
                    "systemctl command not found, cannot check Web UI service active state."
                )
                return False
            try:
                process = subprocess.run(
                    [
                        systemctl_cmd,
                        "--user",
                        "is-active",
                        self._WEB_SERVICE_SYSTEMD_NAME,
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                is_active = (
                    process.returncode == 0 and process.stdout.strip() == "active"
                )
                logger.debug(
                    f"Web UI service '{self._WEB_SERVICE_SYSTEMD_NAME}' active status: {process.stdout.strip()} -> {is_active}"
                )
                return is_active
            except Exception as e:
                logger.error(
                    f"Error checking Web UI systemd active status: {e}", exc_info=True
                )
                return False
        elif os_type == "Windows":
            self._ensure_windows_for_web_service("is_web_service_active")
            sc_cmd = shutil.which("sc.exe")
            if not sc_cmd:
                logger.warning(
                    "sc.exe command not found, cannot check Web UI service active state."
                )
                return False
            try:
                # Use 'sc query' to check the state of the service.
                result = subprocess.check_output(
                    [sc_cmd, "query", self._WEB_SERVICE_WINDOWS_NAME_INTERNAL],
                    text=True,
                    stderr=subprocess.DEVNULL,
                    creationflags=getattr(
                        subprocess, "CREATE_NO_WINDOW", 0
                    ),  # CREATE_NO_WINDOW for Windows
                )
                is_running = "STATE" in result and "RUNNING" in result
                logger.debug(
                    f"Web UI service '{self._WEB_SERVICE_WINDOWS_NAME_INTERNAL}' running state from query: {is_running}"
                )
                return is_running
            except (
                subprocess.CalledProcessError
            ):  # Service does not exist or other sc error
                logger.debug(
                    f"Web UI service '{self._WEB_SERVICE_WINDOWS_NAME_INTERNAL}' not found or error during query."
                )
                return False
            except (
                FileNotFoundError
            ):  # sc.exe not found (should be caught by shutil.which)
                logger.warning("`sc.exe` command not found unexpectedly.")
                return False
            except Exception as e:
                logger.error(
                    f"Error checking Web UI Windows service active status: {e}",
                    exc_info=True,
                )
                return False
        else:
            logger.debug(f"Web UI service active check not supported on OS: {os_type}")
            return False

    def is_web_service_enabled(self) -> bool:
        """Checks if the Web UI system service is enabled for automatic startup.

        Delegates to OS-specific checks:

            - On Linux, uses ``systemctl --user is-enabled`` for the service named
              by :attr:`._WEB_SERVICE_SYSTEMD_NAME`.
            - On Windows, uses ``sc qc`` (query config) for the service named by
              :attr:`._WEB_SERVICE_WINDOWS_NAME_INTERNAL` to check if its start type
              is "AUTO_START".

        Returns ``False`` if the OS is not supported, if system utilities
        (``systemctl``, ``sc.exe``) are not found, or if the service is not enabled.
        Errors during the check are logged.

        Returns:
            bool: ``True`` if the Web UI service is determined to be enabled for
            automatic startup, ``False`` otherwise.
        """
        os_type = self.get_os_type()
        if os_type == "Linux":
            self._ensure_linux_for_web_service("is_web_service_enabled")
            systemctl_cmd = shutil.which("systemctl")
            if not systemctl_cmd:
                logger.warning(
                    "systemctl command not found, cannot check Web UI service enabled state."
                )
                return False
            try:
                process = subprocess.run(
                    [
                        systemctl_cmd,
                        "--user",
                        "is-enabled",
                        self._WEB_SERVICE_SYSTEMD_NAME,
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                # is-enabled can return "enabled", "enabled-runtime", etc.
                # "enabled" means it's set to start. Other statuses might also be considered "on".
                # For simplicity, strict "enabled" check.
                is_enabled = (
                    process.returncode == 0 and process.stdout.strip() == "enabled"
                )
                logger.debug(
                    f"Web UI service '{self._WEB_SERVICE_SYSTEMD_NAME}' enabled status: {process.stdout.strip()} -> {is_enabled}"
                )
                return is_enabled
            except Exception as e:
                logger.error(
                    f"Error checking Web UI systemd enabled status: {e}", exc_info=True
                )
                return False
        elif os_type == "Windows":
            self._ensure_windows_for_web_service("is_web_service_enabled")
            sc_cmd = shutil.which("sc.exe")
            if not sc_cmd:
                logger.warning(
                    "sc.exe command not found, cannot check Web UI service enabled state."
                )
                return False
            try:
                # Use 'sc qc' (query config) to check the start type.
                result = subprocess.check_output(
                    [sc_cmd, "qc", self._WEB_SERVICE_WINDOWS_NAME_INTERNAL],
                    text=True,
                    stderr=subprocess.DEVNULL,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                is_auto_start = (
                    "START_TYPE" in result and "AUTO_START" in result
                )  # 2  AUTO_START
                logger.debug(
                    f"Web UI service '{self._WEB_SERVICE_WINDOWS_NAME_INTERNAL}' auto_start state from qc: {is_auto_start}"
                )
                return is_auto_start
            except (
                subprocess.CalledProcessError
            ):  # Service does not exist or other sc error
                logger.debug(
                    f"Web UI service '{self._WEB_SERVICE_WINDOWS_NAME_INTERNAL}' not found or error during qc."
                )
                return False
            except FileNotFoundError:
                logger.warning("`sc.exe` command not found unexpectedly.")
                return False
            except Exception as e:
                logger.error(
                    f"Error checking Web UI Windows service enabled status: {e}",
                    exc_info=True,
                )
                return False
        else:
            logger.debug(f"Web UI service enabled check not supported on OS: {os_type}")
            return False

    # --- Global Content Directory Management ---
    def _list_content_files(self, sub_folder: str, extensions: List[str]) -> List[str]:
        """
        Internal helper to list files with specified extensions from a sub-folder
        within the global content directory.

        This method constructs a path to ``<content_dir>/<sub_folder>``, then
        scans this directory for files matching any of the provided ``extensions``.
        The global content directory is defined by ``settings['paths.content']``
        and cached in :attr:`._content_dir`.

        Args:
            sub_folder (str): The name of the sub-folder within the global content
                directory to scan (e.g., "worlds", "addons").
            extensions (List[str]): A list of file extensions to search for.
                Extensions should include the leading dot (e.g., ``[".mcworld"]``,
                ``[".mcpack", ".mcaddon"]``).

        Returns:
            List[str]: A sorted list of absolute paths to the files found.
            Returns an empty list if the target directory does not exist or no
            matching files are found.

        Raises:
            AppFileNotFoundError: If the main content directory (:attr:`._content_dir`)
                is not configured or does not exist as a directory.
            FileOperationError: If an OS-level error occurs while scanning the
                directory (e.g., permission issues).
        """
        if not self._content_dir or not os.path.isdir(self._content_dir):
            raise AppFileNotFoundError(str(self._content_dir), "Content directory")

        target_dir = os.path.join(self._content_dir, sub_folder)
        if not os.path.isdir(target_dir):
            logger.debug(
                f"BSM: Content sub-directory '{target_dir}' not found. Returning empty list."
            )
            return []

        found_files: List[str] = []
        for ext in extensions:
            pattern = f"*{ext}" if ext.startswith(".") else f"*.{ext}"
            try:
                for filepath in glob.glob(os.path.join(target_dir, pattern)):
                    if os.path.isfile(filepath):
                        found_files.append(os.path.abspath(filepath))
            except OSError as e:
                raise FileOperationError(
                    f"Error scanning content directory {target_dir}: {e}"
                ) from e
        return sorted(list(set(found_files)))

    def list_available_worlds(self) -> List[str]:
        """Lists available ``.mcworld`` template files from the global content directory.

        This method scans the ``worlds`` sub-folder within the application's
        global content directory (see :attr:`._content_dir` and
        ``settings['paths.content']``) for files with the ``.mcworld`` extension.
        It relies on :meth:`._list_content_files` for the actual scanning.

        These ``.mcworld`` files typically represent world templates that can be
        imported to create new server worlds or overwrite existing ones.

        Returns:
            List[str]: A sorted list of absolute paths to all found ``.mcworld`` files.
            Returns an empty list if the directory doesn't exist or no ``.mcworld``
            files are present.

        Raises:
            AppFileNotFoundError: If the main content directory is not configured
                or found (from :meth:`._list_content_files`).
            FileOperationError: If an OS error occurs during directory scanning
                (from :meth:`._list_content_files`).
        """
        return self._list_content_files("worlds", [".mcworld"])

    def list_available_addons(self) -> List[str]:
        """Lists available addon files (``.mcpack``, ``.mcaddon``) from the global content directory.

        This method scans the ``addons`` sub-folder within the application's
        global content directory (see :attr:`._content_dir` and
        ``settings['paths.content']``) for files with ``.mcpack`` or
        ``.mcaddon`` extensions. It uses :meth:`._list_content_files` for scanning.

        These files represent behavior packs, resource packs, or bundled addons
        that can be installed onto server instances.

        Returns:
            List[str]: A sorted list of absolute paths to all found ``.mcpack``
            and ``.mcaddon`` files. Returns an empty list if the directory
            doesn't exist or no such files are present.

        Raises:
            AppFileNotFoundError: If the main content directory is not configured
                or found (from :meth:`._list_content_files`).
            FileOperationError: If an OS error occurs during directory scanning
                (from :meth:`._list_content_files`).
        """
        return self._list_content_files("addons", [".mcpack", ".mcaddon"])

    # --- Application / System Information ---
    def get_app_version(self) -> str:
        """Returns the application's version string.

        The version is typically derived from the application's settings
        during manager initialization and stored in :attr:`._app_version`.

        Returns:
            str: The application version string (e.g., "1.2.3").
        """
        return self._app_version

    def get_os_type(self) -> str:
        """Returns the current operating system type string.

        This method uses :func:`platform.system()` to determine the OS.
        Common return values include "Linux", "Windows", "Darwin" (for macOS).

        Returns:
            str: A string representing the current operating system.
        """
        return platform.system()

    def _check_system_capabilities(self) -> Dict[str, bool]:
        """
        Internal helper to check for the availability of external OS-level
        dependencies and report their status.

        This method is called during :meth:`.__init__` to determine if optional
        system utilities, required for certain features, are present.
        Currently, it checks for:

            - 'scheduler': ``crontab`` (Linux) or ``schtasks`` (Windows).
            - 'service_manager': ``systemctl`` (Linux) or ``sc.exe`` (Windows).

        The results are stored in the :attr:`.capabilities` dictionary.

        Returns:
            Dict[str, bool]: A dictionary where keys are capability names
            (e.g., "scheduler", "service_manager") and values are booleans
            indicating if the corresponding utility was found.
        """
        caps = {
            "scheduler": False,  # For crontab or schtasks
            "service_manager": False,  # For systemctl
        }
        os_name = self.get_os_type()

        if os_name == "Linux":
            if shutil.which("crontab"):
                caps["scheduler"] = True
            if shutil.which("systemctl"):
                caps["service_manager"] = True

        elif os_name == "Windows":
            if shutil.which("schtasks"):
                caps["scheduler"] = True
            # Eventual support for Windows service management
            if shutil.which("sc.exe"):
                caps["service_manager"] = True

        logger.debug(f"System capability check results: {caps}")
        return caps

    def _log_capability_warnings(self) -> None:
        """
        Internal helper to log warnings if essential system capabilities are missing.

        Called during :meth:`.__init__` after :meth:`._check_system_capabilities`.
        It inspects the :attr:`.capabilities` attribute and logs a warning message
        for each capability that is found to be unavailable. This informs the user
        that certain application features might be disabled or limited.
        """
        if not self.capabilities["scheduler"]:
            logger.warning(
                "Scheduler command (crontab/schtasks) not found. Scheduling features will be disabled in UIs."
            )

        if self.get_os_type() == "Linux" and not self.capabilities["service_manager"]:
            logger.warning(
                "systemctl command not found. Systemd service features will be disabled in UIs."
            )

    @property
    def can_schedule_tasks(self) -> bool:
        """bool: Indicates if a system task scheduler (``crontab`` or ``schtasks``) is available.

        This property reflects the 'scheduler' capability checked during manager
        initialization by :meth:`._check_system_capabilities`. If ``True``,
        features related to scheduled tasks (like automated backups) can be
        expected to work.
        """
        return self.capabilities["scheduler"]

    @property
    def can_manage_services(self) -> bool:
        """bool: Indicates if a system service manager (``systemctl`` or ``sc.exe``) is available.

        This property reflects the 'service_manager' capability checked during
        manager initialization by :meth:`._check_system_capabilities`. If ``True``,
        features related to managing system services (for the Web UI or game servers)
        can be expected to work.
        """
        return self.capabilities["service_manager"]

    # --- Server Discovery ---
    def validate_server(self, server_name: str) -> bool:
        """Validates if a given server name corresponds to a valid installation.

        This method checks for the existence and basic integrity of a server
        installation. It instantiates a :class:`~.core.bedrock_server.BedrockServer`
        object for the given ``server_name`` and then calls its
        :meth:`~.core.bedrock_server.BedrockServer.is_installed` method.

        Any exceptions raised during the instantiation or validation process (e.g.,
        :class:`~.error.InvalidServerNameError`, :class:`~.error.ConfigurationError`)
        are caught, logged as a warning, and result in a ``False`` return value,
        making this a safe check.

        Args:
            server_name (str): The name of the server to validate. This should
                correspond to a subdirectory within the main server base directory.

        Returns:
            bool: ``True`` if the server exists and is a valid installation
            (i.e., its directory and executable are found), ``False`` otherwise.

        Raises:
            MissingArgumentError: If ``server_name`` is an empty string.
        """
        if not server_name:
            raise MissingArgumentError("Server name cannot be empty for validation.")

        logger.debug(
            f"BSM: Validating server '{server_name}' using BedrockServer class."
        )
        try:
            server_instance = BedrockServer(
                server_name=server_name,
                settings_instance=self.settings,
                manager_expath=self._expath,
            )
            is_valid = server_instance.is_installed()
            if is_valid:
                logger.debug(f"BSM: Server '{server_name}' validation successful.")
            else:
                logger.debug(
                    f"BSM: Server '{server_name}' validation failed (directory or executable missing)."
                )
            return is_valid
        except (
            ValueError,
            MissingArgumentError,
            ConfigurationError,
            InvalidServerNameError,
            Exception,
        ) as e_val:
            # Treat any error during instantiation or validation as a failure.
            logger.warning(
                f"BSM: Validation failed for server '{server_name}' due to an error: {e_val}"
            )
            return False

    def get_servers_data(self) -> Tuple[List[Dict[str, Any]], List[str]]:
        """Discovers and retrieves status data for all valid server instances.

        This method scans the main server base directory (defined by
        ``settings['paths.servers']``) for subdirectories that represent server
        installations. For each potential server, it:

            1. Instantiates a :class:`~.core.bedrock_server.BedrockServer` object.
            2. Validates the installation using the server's :meth:`~.core.bedrock_server.BedrockServer.is_installed` method.
            3. If valid, it queries the server's status and version using
               :meth:`~.core.bedrock_server.BedrockServer.get_status` and
               :meth:`~.core.bedrock_server.BedrockServer.get_version`.

        Errors encountered while processing individual servers are collected and
        returned separately, allowing the method to succeed even if some server
        directories are corrupted or misconfigured. The final list of server
        data is sorted alphabetically by server name.

        Returns:
            Tuple[List[Dict[str, Any]], List[str]]: A tuple containing two lists:

                - The first list contains dictionaries, one for each successfully
                  processed server. Each dictionary has the keys:

                    - ``"name"`` (str): The name of the server.
                    - ``"status"`` (str): The server's current status (e.g., "RUNNING", "STOPPED").
                    - ``"version"`` (str): The detected version of the server.

                - The second list contains string messages describing any errors that
                  occurred while processing specific server candidates.

        Raises:
            AppFileNotFoundError: If the main server base directory
                (``settings['paths.servers']``) is not configured or does not exist.
        """
        servers_data: List[Dict[str, Any]] = []
        error_messages: List[str] = []

        if not self._base_dir or not os.path.isdir(self._base_dir):
            raise AppFileNotFoundError(str(self._base_dir), "Server base directory")

        for server_name_candidate in os.listdir(self._base_dir):
            potential_server_path = os.path.join(self._base_dir, server_name_candidate)
            if not os.path.isdir(potential_server_path):
                continue

            try:
                # Instantiate a BedrockServer to leverage its encapsulated logic.
                server = BedrockServer(
                    server_name=server_name_candidate,
                    settings_instance=self.settings,
                    manager_expath=self._expath,
                )

                # Use the instance's own method to validate its installation.
                if not server.is_installed():
                    logger.debug(
                        f"Skipping '{server_name_candidate}': Not a valid server installation."
                    )
                    continue

                # Use the instance's methods to get its current state.
                status = server.get_status()
                version = server.get_version()
                servers_data.append(
                    {"name": server.server_name, "status": status, "version": version}
                )

            except (
                FileOperationError,
                ConfigurationError,
                InvalidServerNameError,
            ) as e:
                msg = f"Could not get info for server '{server_name_candidate}': {e}"
                logger.warning(msg)
                error_messages.append(msg)
            except Exception as e:
                msg = f"An unexpected error occurred while processing server '{server_name_candidate}': {e}"
                logger.error(msg, exc_info=True)
                error_messages.append(msg)

        # Sort the final list alphabetically by server name for consistent output.
        servers_data.sort(key=lambda s: s.get("name", "").lower())
        return servers_data, error_messages
