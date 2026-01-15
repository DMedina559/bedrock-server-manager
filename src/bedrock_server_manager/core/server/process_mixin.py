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
import os
import platform
import subprocess
import time
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    # This helps type checkers understand psutil types without making it a hard dependency.
    import psutil as psutil_for_types


# Local application imports.
from ...error import (
    BSMError,
    MissingArgumentError,
    SendCommandError,
    ServerNotRunningError,
    ServerStartError,
    ServerStopError,
)
from ..system import base as system_base
from ..system import process as system_process
from .base_server_mixin import BedrockServerBaseMixin


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
        self._process: Optional[subprocess.Popen] = None
        self.intentionally_stopped: bool = True
        self.failure_count: int = 0
        self.start_time: float = 0

    def is_running(self) -> bool:
        """Checks if the Bedrock server process is currently running and verified."""
        self.logger.debug(f"Checking if server '{self.server_name}' is running.")
        if self._process is not None and self._process.poll() is None:
            return True
        return system_base.is_server_running(
            self.server_name, self.server_dir, self.app_config_dir
        )

    def send_command(self, command: str) -> None:
        """Sends a command string to the running Bedrock server process."""
        if not command:
            raise MissingArgumentError("Command cannot be empty.")

        if not self.is_running():
            raise ServerNotRunningError(
                f"Cannot send command: Server '{self.server_name}' is not running."
            )

        if self._process is None:
            raise SendCommandError(
                f"Cannot send command to '{self.server_name}': no process handle."
            )

        self.logger.info(
            f"Sending command '{command}' to server '{self.server_name}'..."
        )

        try:
            self._process.stdin.write(f"{command}\n".encode())
            self._process.stdin.flush()
            self.logger.info(
                f"Command '{command}' sent successfully to server '{self.server_name}'."
            )
        except Exception as e_unexp:
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

        output_file = os.path.join(self.server_dir, "server_output.txt")
        pid_file_path = self.get_pid_file_path()

        if os.path.exists(pid_file_path):
            self.logger.error(
                f"Attempted to start server '{self.server_name}', but a PID file already exists at '{pid_file_path}'."
            )
            raise ServerStartError(f"Server '{self.server_name}' has a stale PID file.")

        try:
            with open(output_file, "ab") as f:
                self._process = subprocess.Popen(
                    [self.bedrock_executable_path],
                    cwd=self.server_dir,
                    stdin=subprocess.PIPE,
                    stdout=f,
                    stderr=subprocess.STDOUT,
                    creationflags=(
                        subprocess.CREATE_NO_WINDOW
                        if platform.system() == "Windows"
                        else 0
                    ),
                )

            system_process.write_pid_to_file(pid_file_path, self._process.pid)
            self.intentionally_stopped = False
            self.start_time = time.time()

            if hasattr(self, "set_status_in_config"):
                self.set_status_in_config("RUNNING")
            self.logger.info(
                f"Server '{self.server_name}' has been started with PID {self._process.pid}."
            )
        except FileNotFoundError:
            if hasattr(self, "set_status_in_config"):
                self.set_status_in_config("ERROR")
            self.logger.error(
                f"Executable not found for server '{self.server_name}' at path '{self.bedrock_executable_path}'."
            )
            raise ServerStartError(
                f"Executable not found for server '{self.server_name}'."
            )
        except Exception as e:
            if hasattr(self, "set_status_in_config"):
                self.set_status_in_config("ERROR")
            self.logger.error(
                f"Failed to start server '{self.server_name}': {e}", exc_info=True
            )
            raise ServerStartError(f"Failed to start server '{self.server_name}': {e}")

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

        if self._process is None:
            # If we don't have a process handle, try to find it via system call
            # This is a fallback for when the app restarts but the server process is still running
            verified_process = system_process.get_verified_bedrock_process(
                self.server_name, self.server_dir, self.app_config_dir
            )
            if verified_process:
                self._process = verified_process
            else:
                raise ServerStopError(
                    f"Cannot stop server '{self.server_name}': process handle not found and could not be verified."
                )

        try:
            if hasattr(self, "set_status_in_config"):
                self.set_status_in_config("STOPPING")
        except Exception as e_stat:
            self.logger.warning(
                f"Failed to set status to STOPPING for '{self.server_name}': {e_stat}"
            )

        self.logger.info(f"Attempting to stop server '{self.server_name}'...")

        try:
            self.logger.info(f"Sending 'stop' command to server '{self.server_name}'.")
            self._process.stdin.write(b"stop\n")
            self._process.stdin.flush()
            timeout = self.settings.get("SERVER_STOP_TIMEOUT_SEC", 60)
            self._process.wait(timeout=timeout)
            self.logger.info(f"Server '{self.server_name}' stopped gracefully.")
        except (subprocess.TimeoutExpired, OSError, BrokenPipeError) as e:
            self.logger.warning(
                f"Server '{self.server_name}' did not stop gracefully or pipe was already closed. Killing process. Error: {e}"
            )
            self._process.kill()
        except Exception as e:
            self.logger.error(
                f"An error occurred while stopping server '{self.server_name}': {e}",
                exc_info=True,
            )
            self._process.kill()

        self._process = None
        self.intentionally_stopped = True

        pid_file_path = self.get_pid_file_path()
        system_process.remove_pid_file_if_exists(pid_file_path)

        if hasattr(self, "set_status_in_config"):
            self.set_status_in_config("STOPPED")
        self.logger.info(f"Server '{self.server_name}' stopped successfully.")

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
