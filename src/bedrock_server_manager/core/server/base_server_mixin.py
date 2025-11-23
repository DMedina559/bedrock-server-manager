# bedrock_server_manager/core/server/base_server_mixin.py
"""Provides the foundational :class:`.BedrockServerBaseMixin` class.

This mixin is the first in the inheritance chain for the main
:class:`~.core.bedrock_server.BedrockServer` class. Its primary responsibility
is to initialize core attributes that are common across all server-related
operations, such as server name, directory paths, application settings, and
the logger. All other mixins should inherit from this class to ensure these
fundamental attributes are available.
"""
import os
import platform
import logging
import subprocess
import threading
from typing import Optional, Any
from functools import cached_property

# Local application imports.
from ..system import base as system_base
from ...config.settings import Settings
from ...error import MissingArgumentError, ConfigurationError


class BedrockServerBaseMixin:
    """Initializes fundamental attributes for a Bedrock server instance.

    This mixin serves as the primary base for the main
    :class:`~.core.bedrock_server.BedrockServer` class and, by extension,
    all other server-specific mixins. Its main role is to set up essential
    instance attributes that are shared and used across various server operations.
    These include the server's name, paths to its directories, application
    settings, a dedicated logger, and OS type.

    It is crucial that any class inheriting from this mixin (directly or
    indirectly) calls ``super().__init__(*args, **kwargs)`` in its own
    constructor to ensure the proper initialization chain for cooperative
    multiple inheritance.

    Attributes:
        server_name (str): The unique name of this server instance.
        settings (Settings): The application's settings object.
        logger (logging.Logger): A logger instance for this class.
        base_dir (str): The root directory where all server instances are stored.
        server_dir (str): The specific directory for this server instance's files.
        app_config_dir (str): The application's main configuration directory.
        os_type (str): The current operating system type (e.g., "Windows", "Linux").
        _resource_monitor (system_base.ResourceMonitor): Singleton instance for monitoring resources.
    """

    def __init__(
        self,
        server_name: str,
        settings_instance: Settings,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initializes the base attributes for a Bedrock server instance.

        Args:
            server_name (str): The unique name of the server. This name is used
                to derive directory paths and identify the server.
            settings_instance (Settings): A pre-configured
                :class:`~.config.settings.Settings` object.
            *args (Any): Variable length argument list, passed to `super().__init__`
                to support cooperative multiple inheritance.
            **kwargs (Any): Arbitrary keyword arguments, passed to `super().__init__`
                to support cooperative multiple inheritance.

        Raises:
            MissingArgumentError: If `server_name` is not provided (empty or ``None``).
            ConfigurationError: If critical settings required for path determination
                (like ``paths.servers`` or ``config_dir`` from settings) are missing.
        """
        # Call to super() is essential for cooperative multiple inheritance.
        super().__init__(*args, **kwargs)

        if not server_name:
            # A server instance is meaningless without a name.
            raise MissingArgumentError(
                "BedrockServer cannot be initialized without a server_name."
            )

        self.logger: logging.Logger = logging.getLogger(__name__)

        self.server_name: str = server_name
        self.settings = settings_instance

        if self.settings is None:
            raise ConfigurationError("Settings instance is not available.")

        self.logger.debug(
            f"BedrockServerBaseMixin for '{self.server_name}' initialized using settings from: {self.settings.config_path}"
        )

        # Resolve critical paths from settings.
        _base_dir_val = self.settings.get("paths.servers")
        if not _base_dir_val:
            raise ConfigurationError(
                "BASE_DIR not configured in settings. Cannot initialize BedrockServer."
            )
        self.base_dir: str = _base_dir_val

        # The main directory where this server's files are stored.
        self.server_dir: str = os.path.join(self.base_dir, self.server_name)

        # The global application config directory, used for storing server-specific
        # JSON config files, PID files, etc.
        _app_cfg_dir_val = self.settings.config_dir
        if not _app_cfg_dir_val:
            raise ConfigurationError(
                "Application config_dir not available from settings. Cannot initialize BedrockServer."
            )
        self.app_config_dir: str = _app_cfg_dir_val

        # The operating system type (e.g., 'Windows', 'Linux').
        self.os_type: str = platform.system()

        # --- State attributes for other mixins ---
        # These are initialized here but primarily used by other mixins.

        # For process resource monitoring.
        self._resource_monitor = system_base.ResourceMonitor()

        self.logger.debug(
            f"BedrockServerBaseMixin initialized for '{self.server_name}' "
            f"at '{self.server_dir}'. App Config Dir: '{self.app_config_dir}'"
        )

    @cached_property
    def bedrock_executable_name(self) -> str:
        """str: The platform-specific name of the Bedrock server executable.
        Returns "bedrock_server.exe" on Windows, "bedrock_server" otherwise.
        """
        return "bedrock_server.exe" if self.os_type == "Windows" else "bedrock_server"

    @cached_property
    def bedrock_executable_path(self) -> str:
        """str: The full, absolute path to this server's Bedrock executable.
        Constructed by joining `self.server_dir` and `self.bedrock_executable_name`.
        """
        return os.path.join(self.server_dir, self.bedrock_executable_name)

    @cached_property
    def server_log_path(self) -> str:
        """str: The expected absolute path to the server's main output log file.
        Typically ``<server_dir>/server_output.txt``.
        """
        return os.path.join(self.server_dir, "server_output.txt")

    @cached_property
    def server_properties_path(self) -> str:
        """str: The absolute path to this server's ``server.properties`` file."""
        return os.path.join(self.server_dir, "server.properties")

    @cached_property
    def allowlist_json_path(self) -> str:
        """str: The absolute path to this server's ``allowlist.json`` file."""
        return os.path.join(self.server_dir, "allowlist.json")

    @cached_property
    def permissions_json_path(self) -> str:
        """str: The absolute path to this server's ``permissions.json`` file."""
        return os.path.join(self.server_dir, "permissions.json")

    @cached_property
    def server_config_dir(self) -> str:
        """str: The absolute path to this server instance's dedicated configuration subdirectory.
        This is usually ``<app_config_dir>/<server_name>/``, and is intended
        to store server-specific configuration files, PID files, etc.
        The directory itself is not created by this property.
        """
        return os.path.join(self.app_config_dir, self.server_name)

    def _get_server_pid_filename_default(self) -> str:
        """Generates the default standardized PID filename for this Bedrock server.

        Returns:
            str: The PID filename, typically ``bedrock_<server_name>.pid``.
        """
        return f"bedrock_{self.server_name}.pid"

    def get_pid_file_path(self) -> str:
        """Gets the full, absolute path to this server's primary PID file.

        This file is conventionally used to store the process ID of the running
        Bedrock server instance, especially when it's managed as a background
        process or service. The path is constructed using this server's
        :attr:`server_config_dir` and the filename generated by
        :meth:`_get_server_pid_filename_default`.

        Returns:
            str: The absolute path to the PID file.
        """
        pid_filename = self._get_server_pid_filename_default()
        # Ensure server_config_dir (which might not exist yet) is used for path construction
        # The actual creation of this dir is handled by functions that write the PID file.
        current_server_config_dir = self.server_config_dir
        return os.path.join(current_server_config_dir, pid_filename)
