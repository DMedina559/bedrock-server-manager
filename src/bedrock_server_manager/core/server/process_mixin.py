# bedrock_server_manager/core/server/process_mixin.py
"""Provides the :class:`.ServerProcessMixin` for the :class:`~.core.bedrock_server.BedrockServer` class.

This mixin centralizes the logic for managing the Bedrock server's underlying
system process. Its responsibilities include:

    - Starting the server process directly in the foreground (blocking call).
    - Stopping the server process, attempting graceful shutdown before force-killing.
    - Checking the current running status of the server process.
    - Sending commands to a running server (platform-specific IPC mechanisms).
    - Retrieving process resource information (CPU, memory, uptime) if ``psutil``
      is available.

It abstracts platform-specific process management details by delegating to
functions within the :mod:`~.core.system.linux` and
:mod:`~.core.system.windows` modules, as well as using utilities from
:mod:`~.core.system.process` and :mod:`~.core.system.base`.

The availability of ``psutil`` (for :meth:`.ServerProcessMixin.get_process_info`)
is indicated by the :const:`.PSUTIL_AVAILABLE` flag defined in this module.
"""
import time
from typing import Optional, Dict, Any, TYPE_CHECKING, NoReturn

# psutil is an optional dependency, but required for process management.
try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    psutil = None

if TYPE_CHECKING:
    # This helps type checkers understand psutil types without making it a hard dependency.
    import psutil as psutil_for_types


# Local application imports.
from ..system import process as system_process
from .base_server_mixin import BedrockServerBaseMixin
from ...error import (
    ConfigurationError,
    MissingArgumentError,
    ServerNotRunningError,
    ServerStopError,
    SendCommandError,
    FileOperationError,
    ServerStartError,
    SystemError,
    BSMError,
)
from ...instances import get_bedrock_process_manager


class ServerProcessMixin(BedrockServerBaseMixin):
    """Provides methods for managing the Bedrock server's system process.

    This mixin extends :class:`.BedrockServerBaseMixin` and encapsulates the
    functionality related to the lifecycle and interaction with the actual
    Bedrock server executable running as a system process. It includes methods
    for starting (in foreground), stopping, checking the running state, sending
    console commands, and retrieving resource usage information.

    It achieves platform independence by delegating OS-specific operations
    to functions within the :mod:`~.core.system.linux` and
    :mod:`~.core.system.windows` modules, and uses common utilities from
    :mod:`~.core.system.process` and :mod:`~.core.system.base`.

    This mixin assumes that other mixins or the main
    :class:`~.core.bedrock_server.BedrockServer` class will provide methods like
    ``is_installed()`` (from an installation mixin) and state management methods
    like ``set_status_in_config()`` (from :class:`.ServerStateMixin`).
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initializes the ServerProcessMixin.

        Calls ``super().__init__(*args, **kwargs)`` to participate in cooperative
        multiple inheritance. It relies on attributes (e.g., `server_name`, `logger`,
        `settings`, `server_dir`, `app_config_dir`, `os_type`) initialized by
        :class:`.BedrockServerBaseMixin`. It also implicitly depends on methods
        that may be provided by other mixins that form the complete
        :class:`~.core.bedrock_server.BedrockServer` class (e.g.,
        :meth:`~.ServerStateMixin.set_status_in_config`,
        ``is_installed`` from an installation mixin).

        Args:
            *args (Any): Variable length argument list passed to `super()`.
            **kwargs (Any): Arbitrary keyword arguments passed to `super()`.
        """
        super().__init__(*args, **kwargs)
        self.process_manager = get_bedrock_process_manager()

    def is_running(self) -> bool:
        """Checks if the Bedrock server process is currently running and verified."""
        self.logger.debug(f"Checking if server '{self.server_name}' is running.")
        process = self.process_manager.get_server_process(self.server_name)
        return process is not None and process.poll() is None

    def send_command(self, command: str) -> None:
        """Sends a command string to the running Bedrock server process."""
        if not command:
            raise MissingArgumentError("Command cannot be empty.")

        if not self.is_running():
            raise ServerNotRunningError(
                f"Cannot send command: Server '{self.server_name}' is not running."
            )

        self.logger.info(
            f"Sending command '{command}' to server '{self.server_name}'..."
        )

        try:
            self.process_manager.send_command(self.server_name, command)
            self.logger.info(
                f"Command '{command}' sent successfully to server '{self.server_name}'."
            )
        except BSMError:  # Re-raise known BSM errors
            raise
        except Exception as e_unexp:  # Wrap unexpected errors
            raise SendCommandError(
                f"An unexpected error occurred while sending command to '{self.server_name}': {e_unexp}"
            ) from e_unexp

    def start(self) -> None:
        """Starts the Bedrock server process."""
        if not hasattr(self, "is_installed") or not self.is_installed():
            raise ServerStartError(
                f"Cannot start server '{self.server_name}': Not installed or "
                f"invalid installation at {self.server_dir} (is_installed check failed or method missing)."
            )

        if self.is_running():
            self.logger.warning(
                f"Attempted to start server '{self.server_name}' but it is already running."
            )
            raise ServerStartError(f"Server '{self.server_name}' is already running.")

        try:
            if hasattr(self, "set_status_in_config"):
                self.set_status_in_config("STARTING")
        except Exception as e_status:
            self.logger.warning(
                f"Failed to set status to STARTING for '{self.server_name}': {e_status}"
            )

        self.logger.info(f"Attempting to start server '{self.server_name}'...")

        try:
            self.process_manager.start_server(self.server_name)
            if hasattr(self, "set_status_in_config"):
                self.set_status_in_config("RUNNING")
            self.logger.info(f"Server '{self.server_name}' has been started.")
        except BSMError as e_bsm_start:
            self.logger.error(
                f"A known BSM error occurred while starting server '{self.server_name}': {e_bsm_start}",
                exc_info=True,
            )
            if hasattr(self, "set_status_in_config"):
                self.set_status_in_config("ERROR")
            raise ServerStartError(
                f"Failed to start server '{self.server_name}': {e_bsm_start}"
            ) from e_bsm_start
        except Exception as e_unexp_runtime:
            self.logger.error(
                f"An unexpected error occurred while server '{self.server_name}' was running: {e_unexp_runtime}",
                exc_info=True,
            )
            if hasattr(self, "set_status_in_config"):
                self.set_status_in_config("ERROR")
            raise ServerStartError(
                f"Unexpected error during server '{self.server_name}' execution: {e_unexp_runtime}"
            ) from e_unexp_runtime

    def stop(self) -> None:
        """Stops the Bedrock server process gracefully, with a forceful fallback."""
        if not self.is_running():
            self.logger.info(
                f"Attempted to stop server '{self.server_name}', but it is not currently running."
            )
            if hasattr(self, "set_status_in_config"):
                if self.get_status_from_config() != "STOPPED":
                    try:
                        self.set_status_in_config("STOPPED")
                    except Exception as e_stat:
                        self.logger.warning(
                            f"Failed to set status to STOPPED for non-running server '{self.server_name}': {e_stat}"
                        )
            return

        try:
            if hasattr(self, "set_status_in_config"):
                self.set_status_in_config("STOPPING")
        except Exception as e_stat:
            self.logger.warning(
                f"Failed to set status to STOPPING for '{self.server_name}': {e_stat}"
            )

        self.logger.info(f"Attempting to stop server '{self.server_name}'...")

        try:
            self.process_manager.stop_server(self.server_name)
            if hasattr(self, "set_status_in_config"):
                self.set_status_in_config("STOPPED")
            self.logger.info(f"Server '{self.server_name}' stopped successfully.")
        except BSMError as e:
            if hasattr(self, "set_status_in_config"):
                self.set_status_in_config("ERROR")
            raise ServerStopError(
                f"Failed to stop server '{self.server_name}': {e}"
            ) from e

    def get_process_info(self) -> Optional[Dict[str, Any]]:
        """Gets resource usage information (PID, CPU, Memory, Uptime) for the running server process.

        This method first uses
        :func:`~.core.system.process.get_verified_bedrock_process` to locate and
        verify the Bedrock server process associated with this server instance.
        If a valid process is found, it then uses the :attr:`._resource_monitor`
        (an instance of :class:`~.core.system.base.ResourceMonitor` from the base
        mixin) to calculate its current resource statistics.

        Returns:
            Optional[Dict[str, Any]]: A dictionary containing process information
            if the server is running, verified, and ``psutil`` is available.
            The dictionary has keys: "pid", "cpu_percent", "memory_mb", "uptime".
            Returns ``None`` if the server is not running, cannot be verified,
            ``psutil`` is unavailable, or if an error occurs during statistics retrieval.
            Example: ``{"pid": 1234, "cpu_percent": 15.2, "memory_mb": 256.5, "uptime": "0:10:30"}``
        """
        try:
            # 1. Find and verify the process.
            # get_verified_bedrock_process handles cases where psutil might not be available.
            process_obj: Optional["psutil_for_types.Process"] = (
                system_process.get_verified_bedrock_process(
                    self.server_name, self.server_dir, self.app_config_dir
                )
            )

            if process_obj is None:
                self.logger.debug(
                    f"No verified process found for server '{self.server_name}' to get info."
                )
                return None

            # 2. Delegate the measurement of the found process to the resource monitor.
            # _resource_monitor is initialized in BedrockServerBaseMixin.
            # It also checks for PSUTIL_AVAILABLE.
            return self._resource_monitor.get_stats(process_obj)

        except (
            BSMError
        ) as e_bsm:  # Catch known BSM errors, e.g. from get_verified_bedrock_process
            self.logger.warning(
                f"Known error while trying to get process info for '{self.server_name}': {e_bsm}"
            )
            return None
        except Exception as e_unexp:  # Catch any other unexpected errors
            self.logger.error(
                f"Unexpected error getting process info for '{self.server_name}': {e_unexp}",
                exc_info=True,
            )
            return None
