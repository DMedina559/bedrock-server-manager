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
from ..config import Settings
from ..context import AppContext
from ..config import EXPATH, app_name_title, package_name
from ..error import (
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
from .manager_mixins.player_mixin import PlayerMixin
from .manager_mixins.web_process_mixin import WebProcessMixin
from .manager_mixins.web_service_mixin import WebServiceMixin
from .manager_mixins.content_mixin import ContentMixin
from .manager_mixins.system_mixin import SystemMixin
from .manager_mixins.discovery_mixin import DiscoveryMixin

if platform.system() == "Linux":
    from .system import linux as system_linux_utils
elif platform.system() == "Windows":
    from .system import windows as system_windows_utils

logger = logging.getLogger(__name__)


class BedrockServerManager(
    PlayerMixin,
    WebProcessMixin,
    WebServiceMixin,
    ContentMixin,
    SystemMixin,
    DiscoveryMixin,
):
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

    def __init__(self, settings: Settings) -> None:
        """
        Initializes the BedrockServerManager instance.

        This constructor sets up the manager by:

            1. Accepting an instance of the :class:`~.config.settings.Settings`
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
            settings (Settings): An instance of the application's
                :class:`~.config.settings.Settings` object.

        Raises:
            ConfigurationError: If the provided :class:`~.config.settings.Settings`
                object is misconfigured (e.g., missing critical path definitions like
                ``paths.servers`` or ``paths.content``), or if core application
                constants cannot be accessed.
        """
        self.settings = settings
        self.capabilities = {}
        self._config_dir = None
        self._app_data_dir = None
        self._app_name_title = None
        self._package_name = None
        self._expath = None
        self._base_dir = None
        self._content_dir = None
        self._app_version = "0.0.0"
        self._WEB_SERVER_PID_FILENAME = "web_server.pid"
        self._WEB_SERVER_START_ARG = ["web", "start"]
        self._WEB_SERVICE_SYSTEMD_NAME = "bedrock-server-manager-webui.service"
        self._WEB_SERVICE_WINDOWS_NAME_INTERNAL = "BedrockServerManagerWebUI"
        self._WEB_SERVICE_WINDOWS_DISPLAY_NAME = "Bedrock Server Manager Web UI"

    def load(self):
        """Loads the manager's settings and capabilities."""
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

    def reload(self):
        """Reloads the manager's settings and capabilities."""
        self.load()

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
