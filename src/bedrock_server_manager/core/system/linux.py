# bedrock_server_manager/core/system/linux.py
"""Provides Linux-specific implementations for system process and service management.

This module is tailored for Linux environments and focuses on two main areas:
    1.  **Systemd User Service Management**: Functions for creating, enabling,
        disabling, and checking the existence of systemd user services. These
        are typically used to manage Bedrock servers as background daemons that
        can start on user login. Operations usually involve interaction with
        ``systemctl --user``.
    2.  **Foreground Process Management with FIFO IPC**: Functions for starting
        a Bedrock server directly in the foreground, along with mechanisms for
        Inter-Process Communication (IPC) using a Unix named pipe (FIFO). This
        allows sending commands to the running foreground server.

Key Functionality Groups:

    - **Systemd User Service Utilities** (Linux-specific):
        - :func:`.get_systemd_user_service_file_path`
        - :func:`.check_service_exists`
        - :func:`.create_systemd_service_file`
        - :func:`.enable_systemd_service`
        - :func:`.disable_systemd_service`
    - **Foreground Server Management & IPC** (Linux-specific):
        - :func:`._linux_start_server`
        - :func:`._linux_send_command`
        - :func:`._linux_stop_server`
        - Internal helpers for FIFO listener threads (:func:`._main_pipe_server_listener_thread`)
          and OS signal handling (:func:`._handle_os_signals`).

Constants:
    - :const:`.BEDROCK_EXECUTABLE_NAME`: The typical name of the Bedrock server executable on Linux.
    - :const:`.PIPE_NAME_TEMPLATE`: Template for FIFO paths used for IPC.

Global State:
    - :data:`._foreground_server_shutdown_event`: A threading event for managing
      the lifecycle of foreground server processes.

Note:
    Most functions in this module will perform a platform check and may return
    early or behave differently if not run on a Linux system.
"""

import platform
import os
import re
import signal
import threading
import logging
import subprocess
import shutil
import time
from typing import Optional, Any

# Local application imports.
from . import process as core_process
from ...config import SERVER_TIMEOUT
from ...error import (
    CommandNotFoundError,
    ServerNotRunningError,
    SendCommandError,
    SystemError,
    ServerStartError,
    ServerStopError,
    MissingArgumentError,
    PermissionsError,
    FileOperationError,
    AppFileNotFoundError,
)

logger = logging.getLogger(__name__)


# --- Systemd Service Management ---
def get_systemd_user_service_file_path(service_name_full: str) -> str:
    """Generates the standard path for a systemd user service file on Linux.

    Systemd user service files are typically located in the user's
    ``~/.config/systemd/user/`` directory. This function constructs that path.
    If the provided `service_name_full` does not end with ".service",
    the suffix is automatically appended.

    Args:
        service_name_full (str): The full name of the service unit.
            It can be provided with or without the ``.service`` suffix
            (e.g., "my-app.service" or "my-app").

    Returns:
        str: The absolute path to where the systemd user service file should
        be located (e.g., "/home/user/.config/systemd/user/my-app.service").

    Raises:
        MissingArgumentError: If `service_name_full` is empty or not a string.
    """
    if not isinstance(service_name_full, str) or not service_name_full:
        raise MissingArgumentError(
            "Full service name cannot be empty and must be a string."
        )

    name_to_use = (
        service_name_full
        if service_name_full.endswith(".service")
        else f"{service_name_full}.service"
    )
    # User service files are typically located in ~/.config/systemd/user/
    return os.path.join(
        os.path.expanduser("~"), ".config", "systemd", "user", name_to_use
    )


def check_service_exists(service_name_full: str) -> bool:
    """Checks if a systemd user service file exists on Linux.

    This function determines if a service is defined by checking for the
    presence of its service unit file in the standard systemd user directory
    (obtained via :func:`.get_systemd_user_service_file_path`).

    Args:
        service_name_full (str): The full name of the service unit to check
            (e.g., "my-app.service" or "my-app").

    Returns:
        bool: ``True`` if the service file exists, ``False`` otherwise.
        Returns ``False`` if the current operating system is not Linux.

    Raises:
        MissingArgumentError: If `service_name_full` is empty or not a string.
    """
    if platform.system() != "Linux":
        logger.debug(
            "check_service_exists: Not Linux. Systemd check not applicable, returning False."
        )
        return False
    if not isinstance(service_name_full, str) or not service_name_full:
        raise MissingArgumentError(
            "Full service name cannot be empty and must be a string for service file check."
        )

    service_file_path = get_systemd_user_service_file_path(service_name_full)
    logger.debug(
        f"Checking for systemd user service file existence: '{service_file_path}'"
    )
    exists = os.path.isfile(service_file_path)
    logger.debug(f"Service file '{service_file_path}' exists: {exists}")
    return exists


def create_systemd_service_file(
    service_name_full: str,
    description: str,
    working_directory: str,
    exec_start_command: str,
    exec_stop_command: Optional[str] = None,
    exec_start_pre_command: Optional[str] = None,
    service_type: str = "forking",
    restart_policy: str = "on-failure",
    restart_sec: int = 10,
    after_targets: str = "network.target",
) -> None:
    """Creates or updates a systemd user service file on Linux and reloads the daemon.

    This function generates a systemd service unit file with the specified
    parameters and places it in the user's systemd directory (typically
    ``~/.config/systemd/user/``). After writing the file, it executes
    ``systemctl --user daemon-reload`` to ensure systemd recognizes any changes.

    If the function is called on a non-Linux system, it logs a warning and returns.

    Args:
        service_name_full (str): The full name for the service unit file
            (e.g., "my-app.service" or "my-app", ".service" suffix is optional).
        description (str): A human-readable description for the service.
            Used for the ``Description=`` field in the unit file.
        working_directory (str): The absolute path to the working directory for
            the service process. Used for ``WorkingDirectory=``.
        exec_start_command (str): The command (with arguments) to execute when
            the service starts. Used for ``ExecStart=``.
        exec_stop_command (Optional[str], optional): The command to execute when
            the service stops. Used for ``ExecStop=``. Defaults to ``None``.
        exec_start_pre_command (Optional[str], optional): A command to execute
            before the main ``ExecStart`` command. Used for ``ExecStartPre=``.
            Defaults to ``None``.
        service_type (str, optional): The systemd service type (e.g., "simple",
            "forking", "oneshot"). Used for ``Type=``. Defaults to "forking".
        restart_policy (str, optional): The systemd ``Restart=`` policy
            (e.g., "no", "on-success", "on-failure", "always"). Defaults to "on-failure".
        restart_sec (int, optional): Time in seconds to wait before restarting
            the service if `restart_policy` is active. Used for ``RestartSec=``.
            Defaults to 10.
        after_targets (str, optional): Specifies other systemd units that this
            service should start after. Used for ``After=``.
            Defaults to "network.target".

    Raises:
        MissingArgumentError: If any of `service_name_full`, `description`,
            `working_directory`, or `exec_start_command` are empty or not strings.
        AppFileNotFoundError: If the specified `working_directory` does not exist
            or is not a directory.
        FileOperationError: If creating the systemd user directory or writing
            the service file fails (e.g., due to permissions).
        CommandNotFoundError: If the ``systemctl`` command is not found in the system's PATH.
        SystemError: If ``systemctl --user daemon-reload`` fails.
    """
    if platform.system() != "Linux":
        logger.warning(
            f"Generic systemd service creation skipped: Not Linux. Service: '{service_name_full}'"
        )
        return

    if not all([service_name_full, description, working_directory, exec_start_command]):
        raise MissingArgumentError(
            "service_name_full, description, working_directory, and exec_start_command are required."
        )
    if not os.path.isdir(working_directory):
        raise AppFileNotFoundError(working_directory, "WorkingDirectory")

    name_to_use = (
        service_name_full
        if service_name_full.endswith(".service")
        else f"{service_name_full}.service"
    )
    systemd_user_dir = os.path.join(
        os.path.expanduser("~"), ".config", "systemd", "user"
    )
    service_file_path = os.path.join(systemd_user_dir, name_to_use)

    logger.info(
        f"Creating/Updating generic systemd user service file: '{service_file_path}'"
    )

    try:
        os.makedirs(systemd_user_dir, exist_ok=True)
    except OSError as e:
        raise FileOperationError(
            f"Failed to create systemd user directory '{systemd_user_dir}': {e}"
        ) from e

    # Build the service file content.
    exec_start_pre_line = (
        f"ExecStartPre={exec_start_pre_command}" if exec_start_pre_command else ""
    )
    exec_stop_line = f"ExecStop={exec_stop_command}" if exec_stop_command else ""

    service_content = f"""[Unit]
Description={description}
After={after_targets}

[Service]
Type={service_type}
WorkingDirectory={working_directory}
{exec_start_pre_line}
ExecStart={exec_start_command}
{exec_stop_line}
Restart={restart_policy}
RestartSec={restart_sec}s

[Install]
WantedBy=default.target
"""
    # Remove empty lines that might occur if optional commands are not provided.
    service_content = "\n".join(
        [line for line in service_content.splitlines() if line.strip()]
    )

    try:
        with open(service_file_path, "w", encoding="utf-8") as f:
            f.write(service_content)
        logger.info(
            f"Successfully wrote generic systemd service file: {service_file_path}"
        )
    except OSError as e:
        raise FileOperationError(
            f"Failed to write service file '{service_file_path}': {e}"
        ) from e

    # Reload systemd daemon to recognize the new/updated file.
    systemctl_cmd = shutil.which("systemctl")
    if not systemctl_cmd:
        raise CommandNotFoundError("systemctl")
    try:
        subprocess.run(
            [systemctl_cmd, "--user", "daemon-reload"],
            check=True,
            capture_output=True,
            text=True,
        )
        logger.info(
            f"Systemd user daemon reloaded successfully for service '{name_to_use}'."
        )
    except subprocess.CalledProcessError as e:
        raise SystemError(
            f"Failed to reload systemd user daemon. Error: {e.stderr}"
        ) from e


def enable_systemd_service(service_name_full: str) -> None:
    """Enables a systemd user service on Linux to start on user login.

    This function uses ``systemctl --user enable <service_name>`` to enable
    the specified service. It first checks if the service file exists and
    if the service is already enabled to avoid redundant operations.

    If the function is called on a non-Linux system, it returns early.

    Args:
        service_name_full (str): The full name of the service unit to enable
            (e.g., "my-app.service" or "my-app").

    Raises:
        MissingArgumentError: If `service_name_full` is empty or not a string.
        CommandNotFoundError: If the ``systemctl`` command is not found.
        SystemError: If the service unit file (checked by :func:`.check_service_exists`)
            does not exist, or if the ``systemctl enable`` command fails.
    """
    if platform.system() != "Linux":
        logger.debug(
            "enable_systemd_service: Not Linux. Systemd operation not applicable."
        )
        return
    if not isinstance(service_name_full, str) or not service_name_full:
        raise MissingArgumentError(
            "Full service name cannot be empty and must be a string."
        )

    name_to_use = (
        service_name_full
        if service_name_full.endswith(".service")
        else f"{service_name_full}.service"
    )
    logger.info(f"Attempting to enable systemd user service '{name_to_use}'...")

    systemctl_cmd = shutil.which("systemctl")
    if not systemctl_cmd:
        raise CommandNotFoundError("systemctl")

    if not check_service_exists(name_to_use):
        raise SystemError(
            f"Cannot enable: Systemd service file for '{name_to_use}' does not exist. "
            "Ensure the service file has been created and daemon-reloaded."
        )

    # Check if already enabled to avoid unnecessary calls.
    try:
        process = subprocess.run(
            [systemctl_cmd, "--user", "is-enabled", name_to_use],
            capture_output=True,
            text=True,
            check=False,  # Don't raise for non-zero exit if not enabled
        )
        status_output = process.stdout.strip().lower()
        logger.debug(
            f"'systemctl --user is-enabled {name_to_use}' output: '{status_output}', return code: {process.returncode}"
        )
        # "enabled" means it's enabled. Other statuses like "disabled", "static", "masked"
        # or an empty output with non-zero exit code mean it's not actively enabled.
        if status_output == "enabled":
            logger.info(f"Service '{name_to_use}' is already enabled.")
            return
    except Exception as e:
        logger.warning(
            f"Could not reliably determine if service '{name_to_use}' is enabled: {e}. "
            "Attempting to enable it anyway.",
            exc_info=True,
        )

    try:
        subprocess.run(
            [systemctl_cmd, "--user", "enable", name_to_use],
            check=True,
            capture_output=True,
            text=True,
        )
        logger.info(f"Systemd service '{name_to_use}' enabled successfully.")
    except subprocess.CalledProcessError as e:
        raise SystemError(
            f"Failed to enable systemd service '{name_to_use}'. Error: {e.stderr.strip()}"
        ) from e


def disable_systemd_service(service_name_full: str) -> None:
    """Disables a systemd user service on Linux from starting on user login.

    This function uses ``systemctl --user disable <service_name>`` to disable
    the specified service. It first checks if the service file exists and
    if the service is already disabled (or not enabled) to avoid errors or
    redundant operations. Static or masked services cannot be disabled this
    way and will be logged accordingly.

    If the function is called on a non-Linux system, it returns early.

    Args:
        service_name_full (str): The full name of the service unit to disable
            (e.g., "my-app.service" or "my-app").

    Raises:
        MissingArgumentError: If `service_name_full` is empty or not a string.
        CommandNotFoundError: If the ``systemctl`` command is not found.
        SystemError: If the ``systemctl disable`` command fails for reasons
            other than the service being static or masked.
    """
    if platform.system() != "Linux":
        logger.debug(
            "disable_systemd_service: Not Linux. Systemd operation not applicable."
        )
        return
    if not isinstance(service_name_full, str) or not service_name_full:
        raise MissingArgumentError(
            "Full service name cannot be empty and must be a string."
        )

    name_to_use = (
        service_name_full
        if service_name_full.endswith(".service")
        else f"{service_name_full}.service"
    )
    logger.info(f"Attempting to disable systemd user service '{name_to_use}'...")

    systemctl_cmd = shutil.which("systemctl")
    if not systemctl_cmd:
        raise CommandNotFoundError("systemctl")

    if not check_service_exists(name_to_use):
        logger.info(  # Changed from debug to info for more visibility on this common case
            f"Service file for '{name_to_use}' does not exist. Assuming already disabled or removed."
        )
        return

    # Check if already disabled or not in an "enabled" state.
    try:
        process = subprocess.run(
            [systemctl_cmd, "--user", "is-enabled", name_to_use],
            capture_output=True,
            text=True,
            check=False,  # Don't raise for non-zero exit
        )
        status_output = process.stdout.strip().lower()
        logger.debug(
            f"'systemctl --user is-enabled {name_to_use}' output: '{status_output}', return code: {process.returncode}"
        )
        # If not "enabled", it's effectively disabled for auto-start or in a state
        # where 'disable' might not apply or is redundant.
        if status_output != "enabled":
            logger.info(
                f"Service '{name_to_use}' is already in a non-enabled state ('{status_output}'). No action needed for disable."
            )
            return
    except Exception as e:
        logger.warning(
            f"Could not reliably determine if service '{name_to_use}' is enabled: {e}. "
            "Attempting to disable it anyway.",
            exc_info=True,
        )

    try:
        subprocess.run(
            [systemctl_cmd, "--user", "disable", name_to_use],
            check=True,
            capture_output=True,
            text=True,
        )
        logger.info(f"Systemd service '{name_to_use}' disabled successfully.")
    except subprocess.CalledProcessError as e:
        stderr_lower = (e.stderr or "").strip().lower()
        # It's not an error if the service is static or masked, as 'disable' doesn't apply.
        if "static" in stderr_lower or "masked" in stderr_lower:
            logger.info(
                f"Service '{name_to_use}' is {stderr_lower.split()[-1]}. "  # Extracts 'static' or 'masked'
                "It cannot be disabled via 'systemctl disable' command."
            )
            return
        raise SystemError(
            f"Failed to disable systemd service '{name_to_use}'. Error: {e.stderr.strip()}"
        ) from e


# --- Constants ---
BEDROCK_EXECUTABLE_NAME = "bedrock_server"
"""The standard filename of the Minecraft Bedrock dedicated server executable on Linux."""

# --- Global State Variables ---
_foreground_server_shutdown_event = threading.Event()
"""A ``threading.Event`` used to signal a shutdown request to all actively managed
foreground server instances (specifically, their main management loops and
FIFO listener threads within :func:`._linux_start_server`).
"""


def _linux_stop_server(server_name: str, config_dir: str) -> None:
    """Stops a Bedrock server on Linux, trying graceful shutdown then PID termination.

    This function attempts to stop a Bedrock server using a two-pronged approach:
        1. **Graceful Shutdown via Pipe**: It first tries to send the "stop" command
           to the server using :func:`._linux_send_command`. If this is successful,
           it assumes the server will shut down cleanly.
        2. **PID Termination**: If sending the "stop" command fails (e.g., because
           the server or its pipe listener is not running, indicated by
           :class:`~bedrock_server_manager.error.ServerNotRunningError` or
           :class:`~bedrock_server_manager.error.SendCommandError`), this function
           falls back to stopping the server by its Process ID (PID). It uses
           :func:`core_process.get_bedrock_server_pid_file_path` and
           :func:`core_process.read_pid_from_file` to find the PID, then
           :func:`core_process.is_process_running` to check if it's active, and
           finally :func:`core_process.terminate_process_by_pid` to stop it.
           Stale PID files are cleaned up.

    Args:
        server_name (str): The name of the server to stop.
        config_dir (str): The application's configuration directory, used to
            locate the server's PID file.

    Raises:
        MissingArgumentError: If `server_name` or `config_dir` are empty.
        ServerStopError: If the fallback PID termination method fails (e.g.,
            cannot read PID file for unexpected reasons, or ``terminate_process_by_pid``
            encounters a critical error).
    """
    if not all([server_name, config_dir]):
        raise MissingArgumentError("server_name and config_dir are required.")

    logger.info(f"Attempting to stop server '{server_name}' on Linux...")

    # First, try the graceful 'stop' command via the pipe.
    try:
        _linux_send_command(server_name, "stop")
        logger.info(
            f"'stop' command sent to '{server_name}'. Please allow time for it to shut down."
        )
        return
    except ServerNotRunningError:
        logger.warning(
            f"Could not send 'stop' command because pipe not found. Attempting to stop by PID."
        )
    except SendCommandError as e:
        logger.error(
            f"Failed to send 'stop' command to '{server_name}': {e}. Attempting to stop by PID."
        )

    # If sending the command fails, fall back to PID termination.
    try:
        pid_file_path = core_process.get_bedrock_server_pid_file_path(
            server_name, config_dir
        )
        pid_to_stop = core_process.read_pid_from_file(pid_file_path)

        if pid_to_stop is None or not core_process.is_process_running(pid_to_stop):
            logger.info(
                f"No running process found for PID from file. Cleaning up stale PID file if it exists."
            )
            core_process.remove_pid_file_if_exists(pid_file_path)
            return

        logger.info(
            f"Found running server '{server_name}' with PID {pid_to_stop}. Terminating process..."
        )
        core_process.terminate_process_by_pid(pid_to_stop)
        core_process.remove_pid_file_if_exists(pid_file_path)
        logger.info(f"Stop-by-PID sequence for server '{server_name}' completed.")

    except (AppFileNotFoundError, FileOperationError):
        logger.info(f"No PID file found for '{server_name}'. Assuming already stopped.")
    except (ServerStopError, SystemError) as e:
        raise ServerStopError(
            f"Failed to stop server '{server_name}' by PID: {e}"
        ) from e
