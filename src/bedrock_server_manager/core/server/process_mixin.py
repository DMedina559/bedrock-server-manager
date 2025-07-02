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
from bedrock_server_manager.core.system import linux as system_linux_proc
from bedrock_server_manager.core.system import windows as system_windows_proc
from bedrock_server_manager.core.system import process as system_process
from bedrock_server_manager.core.server.base_server_mixin import BedrockServerBaseMixin
from bedrock_server_manager.core.system import base as system_base
from bedrock_server_manager.error import (
    ConfigurationError,
    MissingArgumentError,
    CommandNotFoundError,
    ServerNotRunningError,
    ServerStopError,
    SendCommandError,
    FileOperationError,
    ServerStartError,
    SystemError,
    ServerProcessError,
    BSMError,
)


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
        # Attributes like self.server_name, self.server_dir etc. are available from BedrockServerBaseMixin.
        # Methods like self.is_installed() (from InstallUpdateMixin) and
        # self.set_status_in_config() (from ServerStateMixin) are expected to be present
        # on the final composed BedrockServer object.

    def is_running(self) -> bool:
        """Checks if the Bedrock server process is currently running and verified.

        This method delegates to
        :func:`~.core.system.base.is_server_running`, which internally uses
        :func:`~.core.system.process.get_verified_bedrock_process` to check
        not only if a process with the stored PID exists, but also if that
        process matches the expected executable path and working directory for
        this server instance.

        It does not update the server's persisted status in the configuration
        but provides a real-time check of the process state.

        Returns:
            bool: ``True`` if the server process is running and verified,
            ``False`` otherwise. This includes cases where `psutil` might be
            unavailable or if checks fail due to permissions or other system errors.

        Raises:
            ConfigurationError: If the base directory for servers (`paths.servers`)
                is not configured in settings, as this is essential for path
                verification.
        """
        self.logger.debug(f"Checking if server '{self.server_name}' is running.")

        if not self.base_dir:  # From BedrockServerBaseMixin
            raise ConfigurationError(
                "Base server directory ('paths.servers') not configured, cannot check server running status."
            )

        try:
            # system_base.is_server_running itself calls core_process.get_verified_bedrock_process
            is_running_flag = system_base.is_server_running(
                self.server_name, self.server_dir, self.app_config_dir
            )
            self.logger.debug(
                f"system_base.is_server_running for '{self.server_name}' returned: {is_running_flag}"
            )
            return is_running_flag
        except (
            BSMError
        ) as e_bsm:  # Catch known BSM errors that might occur during check
            self.logger.warning(
                f"A known error occurred during is_server_running check for '{self.server_name}': {e_bsm}"
            )
            return False
        except ConfigurationError:
            # Let ConfigurationError propagate as it's critical
            raise
        except Exception as e_unexp:
            # Catch any other unexpected errors and treat as "not running" for safety
            self.logger.error(
                f"Unexpected error during is_server_running check for '{self.server_name}': {e_unexp}",
                exc_info=True,
            )
            return False

    def send_command(self, command: str) -> None:
        """Sends a command string to the running Bedrock server process.

        This method delegates to platform-specific functions for sending commands:

            - On Linux: :func:`~.core.system.linux._linux_send_command` (uses FIFO).
            - On Windows: :func:`~.core.system.windows._windows_send_command` (uses named pipes).

        Args:
            command (str): The command string to send to the server's console
                (e.g., "list", "say Hello World").

        Raises:
            MissingArgumentError: If the `command` string is empty.
            ServerNotRunningError: If :meth:`.is_running` returns ``False`` before
                attempting to send the command.
            NotImplementedError: If the current operating system is not supported
                or if the required system module (linux/windows) is not available.
            SendCommandError: For underlying failures during the send operation
                (e.g., pipe errors, `schtasks` errors).
            CommandNotFoundError: If platform-specific helper commands (like `screen`
                if it were used, or `schtasks` if it was missing but passed init)
                are not found. (More likely caught during scheduler init).
            SystemError: For other unexpected system-level errors during the send.
        """
        if not command:
            raise MissingArgumentError("Command cannot be empty.")

        if not self.is_running():  # Relies on the refined is_running()
            raise ServerNotRunningError(
                f"Cannot send command: Server '{self.server_name}' is not running."
            )

        self.logger.info(
            f"Sending command '{command}' to server '{self.server_name}' on {self.os_type}..."
        )

        try:
            if self.os_type == "Linux":
                if not system_linux_proc:  # Should not happen if correctly imported
                    raise NotImplementedError(
                        "Linux system processing module not available (system_linux_proc)."
                    )
                system_linux_proc._linux_send_command(self.server_name, command)
            elif self.os_type == "Windows":
                if not system_windows_proc:  # Should not happen
                    raise NotImplementedError(
                        "Windows system processing module not available (system_windows_proc)."
                    )
                system_windows_proc._windows_send_command(self.server_name, command)
            else:
                raise NotImplementedError(
                    f"Sending commands is not supported on operating system: {self.os_type}"
                )
            self.logger.info(
                f"Command '{command}' sent successfully to server '{self.server_name}'."
            )
        except BSMError:  # Re-raise known BSM errors
            raise
        except Exception as e_unexp:  # Wrap unexpected errors
            raise SendCommandError(
                f"An unexpected error occurred while sending command to '{self.server_name}': {e_unexp}"
            ) from e_unexp

    def start(self) -> NoReturn:
        """Starts the Bedrock server process directly in the foreground (blocking).

        This method is intended for direct, interactive server execution and will
        block the calling thread until the server process terminates (either
        gracefully or due to a crash). It handles pre-start checks, updates the
        server's status in its configuration, and delegates to platform-specific
        start functions:

            - On Linux: :func:`~.core.system.linux._linux_start_server`.
            - On Windows: :func:`~.core.system.windows._windows_start_server`.

        The server's status is set to "STARTING" before launch and should be
        updated to "RUNNING" by the platform-specific function upon successful
        startup. On termination, this method ensures the status is set to
        "STOPPED" or "ERROR".

        Requires `self.is_installed()` (from another mixin) to be ``True``.

        Raises:
            ServerStartError: If the server is not installed, is already running,
                runs on an unsupported OS, or if any error occurs during the
                startup or execution of the server process. This can wrap
                various underlying exceptions like :class:`~.error.BSMError` or
                :class:`~.error.SystemError`.
        """
        # --- Pre-flight Checks ---
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

        # --- Begin Startup Process ---
        try:
            if hasattr(self, "set_status_in_config"):
                self.set_status_in_config("STARTING")  # type: ignore
            else:
                self.logger.warning(
                    "set_status_in_config method not found; cannot update status to STARTING."
                )
        except Exception as e_status:
            self.logger.warning(
                f"Failed to set status to STARTING for '{self.server_name}': {e_status}"
            )

        self.logger.info(
            f"Attempting a direct (blocking) start for server '{self.server_name}' "
            f"on {self.os_type}..."
        )

        try:
            # --- Platform-Specific Blocking Call ---
            if self.os_type == "Linux":
                system_linux_proc._linux_start_server(
                    self.server_name, self.server_dir, self.app_config_dir
                )
            elif self.os_type == "Windows":
                system_windows_proc._windows_start_server(
                    self.server_name, self.server_dir, self.app_config_dir
                )
            else:
                # This case should ideally be caught earlier if OS is unsupported for any operation.
                if hasattr(self, "set_status_in_config"):
                    self.set_status_in_config("ERROR")  # type: ignore
                raise ServerStartError(
                    f"Unsupported operating system for server start: {self.os_type}"
                )

            self.logger.info(
                f"Direct server session for '{self.server_name}' has ended gracefully."
            )

        except BSMError as e_bsm_start:  # Catch known BSM errors during startup
            self.logger.error(
                f"A known BSM error occurred while starting server '{self.server_name}': {e_bsm_start}",
                exc_info=True,
            )
            if hasattr(self, "set_status_in_config"):
                self.set_status_in_config("ERROR")  # type: ignore
            raise ServerStartError(
                f"Failed to start server '{self.server_name}': {e_bsm_start}"
            ) from e_bsm_start
        except (
            Exception
        ) as e_unexp_runtime:  # Catch unexpected errors during server runtime
            self.logger.error(
                f"An unexpected error occurred while server '{self.server_name}' was running: {e_unexp_runtime}",
                exc_info=True,
            )
            if hasattr(self, "set_status_in_config"):
                self.set_status_in_config("ERROR")  # type: ignore
            raise ServerStartError(
                f"Unexpected error during server '{self.server_name}' execution: {e_unexp_runtime}"
            ) from e_unexp_runtime
        finally:
            # --- Final Status Cleanup ---
            # Check current stored status. If it's still STARTING or RUNNING, correct it.
            if hasattr(self, "get_status_from_config") and hasattr(
                self, "set_status_in_config"
            ):
                current_stored_status = self.get_status_from_config()  # type: ignore
                if current_stored_status not in ("STOPPED", "ERROR"):
                    self.logger.info(
                        f"Server '{self.server_name}' process ended. Correcting stored status from '{current_stored_status}' to STOPPED."
                    )
                    self.set_status_in_config("STOPPED")  # type: ignore
            else:
                self.logger.warning(
                    "Status management methods (get/set_status_in_config) not found; final status may be inaccurate."
                )

    def stop(self) -> None:
        """Stops the Bedrock server process gracefully, with a forceful fallback.

        This method orchestrates the server shutdown sequence:

            1. Checks if the server is running using :meth:`.is_running`. If not,
               ensures the stored status is "STOPPED" and returns.
            2. Sets the server's stored status to "STOPPING".
            3. Attempts a graceful shutdown by sending the "stop" command via
               :meth:`.send_command`.
            4. Waits for the process to terminate, checking its status periodically
               up to a configured timeout (`SERVER_STOP_TIMEOUT_SEC` from settings).
            5. If the server is still running after the timeout, it attempts a
               forceful PID-based termination using utilities from
               :mod:`~.core.system.process`.
            6. Updates the stored status to "STOPPED" upon successful termination,
               or "ERROR" if issues persist.

        Raises:
            ServerStopError: If the server fails to stop after all attempts and
                is still detected as running.
        """
        if not self.is_running():
            self.logger.info(
                f"Attempted to stop server '{self.server_name}', but it is not currently running."
            )
            # Ensure stored status is consistent if is_running is false.
            if hasattr(self, "get_status_from_config") and hasattr(
                self, "set_status_in_config"
            ):
                if self.get_status_from_config() != "STOPPED":  # type: ignore
                    try:
                        self.set_status_in_config("STOPPED")  # type: ignore
                    except Exception as e_stat:
                        self.logger.warning(
                            f"Failed to set status to STOPPED for non-running server '{self.server_name}': {e_stat}"
                        )
            return

        try:
            if hasattr(self, "set_status_in_config"):
                self.set_status_in_config("STOPPING")  # type: ignore
        except Exception as e_stat:  # Should be more specific if possible
            self.logger.warning(
                f"Failed to set status to STOPPING for '{self.server_name}': {e_stat}"
            )

        self.logger.info(f"Attempting to stop server '{self.server_name}'...")

        # --- 1. Attempt graceful shutdown via command ---
        graceful_attempted = False
        try:
            # Ensure send_command method exists (it should if this mixin is used correctly)
            if hasattr(self, "send_command"):
                self.send_command("stop")  # This method is part of ServerProcessMixin
                self.logger.info(f"Sent 'stop' command to server '{self.server_name}'.")
                graceful_attempted = True
            else:
                self.logger.warning(  # Should not happen in normal use
                    "send_command method not found on self. Cannot send graceful stop command."
                )
        except BSMError as e_cmd:  # Catch known BSM errors from send_command
            self.logger.warning(
                f"Failed to send 'stop' command to '{self.server_name}': {e_cmd}. Proceeding to check process status."
            )
        except Exception as e_unexp_cmd:  # Catch any other unexpected error
            self.logger.error(
                f"Unexpected error sending 'stop' command to '{self.server_name}': {e_unexp_cmd}",
                exc_info=True,
            )

        # --- 2. Wait for process to terminate ---
        # Only wait if a graceful stop was attempted, or always wait if is_running was true?
        # Current logic waits regardless, which is fine.
        stop_timeout_sec = self.settings.get("SERVER_STOP_TIMEOUT_SEC", 60)
        # Make max_attempts at least 1 to ensure at least one check after command.
        max_attempts = max(1, stop_timeout_sec // 2)
        sleep_interval = 2  # seconds

        self.logger.info(
            f"Waiting up to {max_attempts * sleep_interval}s for '{self.server_name}' process to terminate..."
        )

        for attempt in range(max_attempts):
            if not self.is_running():
                if hasattr(self, "set_status_in_config"):
                    self.set_status_in_config("STOPPED")  # type: ignore
                self.logger.info(
                    f"Server '{self.server_name}' stopped successfully (detected on attempt {attempt + 1})."
                )
                return

            self.logger.debug(
                f"Waiting for '{self.server_name}' to stop (attempt {attempt + 1}/{max_attempts})..."
            )
            time.sleep(sleep_interval)

        # --- 3. If still running, attempt forceful PID-based termination ---
        if self.is_running():  # Re-check after waiting
            self.logger.error(
                f"Server '{self.server_name}' failed to stop gracefully after command and wait."
            )
            self.logger.info(
                f"Attempting forceful PID-based termination for server '{self.server_name}'."
            )

            # Ensure get_pid_file_path method exists (from BaseServerMixin or similar)
            if not hasattr(self, "get_pid_file_path"):
                self.logger.error(
                    "get_pid_file_path method not found. Cannot perform PID-based termination."
                )
                if hasattr(self, "set_status_in_config"):
                    self.set_status_in_config("ERROR")  # type: ignore
                raise ServerStopError(
                    f"Cannot perform PID-based stop for '{self.server_name}': missing PID file path method."
                )

            pid_file_path = self.get_pid_file_path()  # type: ignore
            try:
                pid_to_terminate = system_process.read_pid_from_file(pid_file_path)
                if pid_to_terminate and system_process.is_process_running(
                    pid_to_terminate
                ):
                    self.logger.info(
                        f"Terminating PID {pid_to_terminate} for '{self.server_name}'."
                    )
                    system_process.terminate_process_by_pid(pid_to_terminate)
                    time.sleep(
                        sleep_interval
                    )  # Give a moment for termination to reflect
                    if not self.is_running():  # Final check
                        if hasattr(self, "set_status_in_config"):
                            self.set_status_in_config("STOPPED")  # type: ignore
                        self.logger.info(
                            f"Server '{self.server_name}' (PID {pid_to_terminate}) forcefully terminated and confirmed stopped."
                        )
                        return
                    else:
                        self.logger.error(
                            f"Server '{self.server_name}' (PID {pid_to_terminate}) STILL RUNNING after forceful termination attempt."
                        )
                elif pid_to_terminate:
                    self.logger.info(
                        f"PID {pid_to_terminate} from file for '{self.server_name}' is not running. Removing stale PID file."
                    )
                    system_process.remove_pid_file_if_exists(pid_file_path)
                    # If it wasn't running by PID, but is_running() said it was, there's a discrepancy.
                    # However, if is_running() now returns false, we're good.
                    if not self.is_running() and hasattr(self, "set_status_in_config"):
                        self.set_status_in_config("STOPPED")  # type: ignore
                    return

            except (
                FileOperationError,
                SystemError,
                ServerStopError,
                MissingArgumentError,
            ) as e_force:
                self.logger.error(
                    f"Error during forceful termination attempt for '{self.server_name}': {e_force}",
                    exc_info=True,
                )
            except Exception as e_unexp_force:
                self.logger.error(
                    f"Unexpected error during forceful termination of '{self.server_name}': {e_unexp_force}",
                    exc_info=True,
                )
        else:  # Was not running after the wait period
            if hasattr(self, "set_status_in_config"):
                self.set_status_in_config("STOPPED")  # type: ignore
            self.logger.info(
                f"Server '{self.server_name}' confirmed stopped after waiting period."
            )
            return

        # --- 4. Final status update and error if still running ---
        if hasattr(self, "get_status_from_config") and hasattr(
            self, "set_status_in_config"
        ):
            if self.get_status_from_config() != "STOPPED":  # type: ignore
                self.set_status_in_config("ERROR")  # type: ignore

        if self.is_running():  # Final check
            raise ServerStopError(
                f"Server '{self.server_name}' failed to stop after all attempts. Manual intervention may be required."
            )
        else:
            # This path means it stopped, but possibly due to forceful kill or after initial command failed.
            # Status should have been set to STOPPED if termination was confirmed.
            # If it's ERROR here, it means forceful termination might have also failed confirmation.
            if hasattr(self, "get_status_from_config") and self.get_status_from_config() != "STOPPED":  # type: ignore
                self.logger.warning(
                    f"Server '{self.server_name}' stopped, but final status in config is not 'STOPPED'. Current: {self.get_status_from_config()}."
                )
                if hasattr(self, "set_status_in_config"):
                    self.set_status_in_config("STOPPED")  # type: ignore

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
