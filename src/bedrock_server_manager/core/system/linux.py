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
from bedrock_server_manager.core.system import process as core_process
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.error import (
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

PIPE_NAME_TEMPLATE = "/tmp/BedrockServerPipe_{server_name}"
"""Template string for creating Unix named pipe (FIFO) paths for IPC.
The ``{server_name}`` placeholder will be replaced by a sanitized server name.
Example: ``/tmp/BedrockServerPipe_MyServer``
"""

# --- Global State Variables ---
_foreground_server_shutdown_event = threading.Event()
"""A ``threading.Event`` used to signal a shutdown request to all actively managed
foreground server instances (specifically, their main management loops and
FIFO listener threads within :func:`._linux_start_server`).
"""


def _handle_os_signals(sig: int, frame: Any) -> None:
    """Signal handler for SIGINT and SIGTERM to initiate graceful shutdown.

    This function is registered as the handler for `signal.SIGINT` and
    `signal.SIGTERM`. When either signal is received, it sets the global
    `_foreground_server_shutdown_event`, which is monitored by the main loop
    in `_linux_start_server` to begin the shutdown sequence.

    Args:
        sig (int): The signal number (e.g., `signal.SIGINT`).
        frame (Any): The current stack frame (unused by this handler).
    """
    logger.info(f"OS Signal {sig} received. Setting foreground shutdown event.")
    _foreground_server_shutdown_event.set()


def _main_pipe_server_listener_thread(
    pipe_path: str,
    bedrock_process: subprocess.Popen,
    server_name: str,
    overall_shutdown_event: threading.Event,
) -> None:
    """Dedicated thread to listen on a named pipe (FIFO) for server commands.

    This function runs in a separate thread when a Bedrock server is started
    in foreground mode via :func:`._linux_start_server`. It opens the FIFO
    specified by `pipe_path` in read mode. Opening a FIFO in read mode typically
    blocks until another process opens it in write mode (a client connects).

    Once a client connects (writes to the pipe), this thread reads commands
    line by line from the pipe. Each command is stripped of whitespace and, if
    not empty, is written to the standard input of the `bedrock_process`.
    This allows external processes to send commands to the Bedrock server.

    The listener loop continues, reopening the pipe for the next client after
    one disconnects, as long as the `overall_shutdown_event` is not set and
    the `bedrock_process` is still running. If the shutdown event is triggered
    or the server process terminates, the listener thread will exit.

    Args:
        pipe_path (str): The absolute filesystem path to the named pipe (FIFO)
            to listen on.
        bedrock_process (subprocess.Popen): The `subprocess.Popen` object for the
            running Bedrock server. Commands are written to its `stdin`.
        server_name (str): The name of the server, used primarily for logging.
        overall_shutdown_event (threading.Event): A `threading.Event` object that
            signals this listener thread to terminate its loop and cleanly exit.
            This is typically set when the main server process is shutting down.
    """
    logger.info(f"MAIN_PIPE_LISTENER: Starting for pipe '{pipe_path}'.")

    while not overall_shutdown_event.is_set() and bedrock_process.poll() is None:
        try:
            logger.info(
                f"MAIN_PIPE_LISTENER: Waiting for a client to connect to '{pipe_path}'..."
            )
            # Opening the pipe in read mode blocks until a client opens it for writing.
            with open(pipe_path, "r") as pipe_file:
                logger.info(f"MAIN_PIPE_LISTENER: Client connected to '{pipe_path}'.")
                # Read commands line by line from the pipe.
                for command_str in pipe_file:
                    if overall_shutdown_event.is_set():
                        break
                    command_str = command_str.strip()
                    if not command_str:
                        continue

                    # Forward the received command to the Bedrock server's stdin.
                    logger.info(
                        f"MAIN_PIPE_LISTENER: Received command: '{command_str}'"
                    )
                    if bedrock_process.stdin and not bedrock_process.stdin.closed:
                        bedrock_process.stdin.write(
                            (command_str + "\n").encode("utf-8")
                        )
                        bedrock_process.stdin.flush()
                    else:
                        logger.warning(
                            f"MAIN_PIPE_LISTENER: Stdin for server '{server_name}' is closed."
                        )
                        break
            if not overall_shutdown_event.is_set():
                logger.info(
                    f"MAIN_PIPE_LISTENER: Client disconnected. Awaiting next connection."
                )
        except Exception as e:
            if overall_shutdown_event.is_set():
                break
            logger.error(
                f"MAIN_PIPE_LISTENER: Unexpected error for '{pipe_path}': {e}",
                exc_info=True,
            )
            time.sleep(1)

    logger.info(
        f"MAIN_PIPE_LISTENER: Main pipe listener thread for '{pipe_path}' has EXITED."
    )


def _linux_start_server(server_name: str, server_dir: str, config_dir: str) -> None:
    """Starts a Bedrock server in the foreground on Linux and manages its lifecycle.

    This function is the Linux equivalent of `_windows_start_server` and is
    intended to be run as the main blocking process when starting a server
    directly (not as a systemd service). It performs the following:

        1. Verifies that another instance of the same server isn't already running
           by checking PID files and process status (using :func:`core_process.get_verified_bedrock_process`).
           Cleans up stale PID files.
        2. Checks that the server executable (`bedrock_server`) exists and is executable.
        3. Creates a Unix named pipe (FIFO) for Inter-Process Communication (IPC) using
           the path from :const:`.PIPE_NAME_TEMPLATE`. Removes any pre-existing FIFO.
        4. Sets up OS signal handlers for `SIGINT` (Ctrl+C) and `SIGTERM` to trigger
           graceful shutdown via :func:`._handle_os_signals`.
        5. Launches the Bedrock server executable as a subprocess.
           - `LD_LIBRARY_PATH` is set to `.` in the subprocess environment to ensure
             it finds its libraries in the server directory.
           - Its stdout/stderr are redirected to `server_output.txt` in the server directory.
        6. Writes the new server process's PID to a ``bedrock_<server_name>.pid`` file
           using :func:`core_process.write_pid_to_file`.
        7. Starts a named pipe server listener thread (:func:`._main_pipe_server_listener_thread`)
           to accept commands for the Bedrock server via the created FIFO.
        8. Enters a blocking loop, waiting for the `_foreground_server_shutdown_event`
           to be set (e.g., by OS signals or if the server process dies).
        9. Upon shutdown, attempts to gracefully stop the Bedrock server by sending
           the "stop" command via its stdin, then waits for it to terminate. If it
           doesn't stop in time, it's forcibly terminated using :func:`core_process.terminate_process_by_pid`.
        10. Cleans up the PID file, FIFO, closes handles, and restores default signal handlers.

    Args:
        server_name (str): The unique name identifier for the server.
        server_dir (str): The absolute path to the server's installation directory,
            where `bedrock_server` is located.
        config_dir (str): The absolute path to the application's configuration
            directory, used for storing the PID file.

    Raises:
        MissingArgumentError: If `server_name`, `server_dir`, or `config_dir` are empty.
        ServerStartError: If the server appears to be already running, or if any
            critical step in launching the server or its IPC mechanism fails.
        AppFileNotFoundError: If `bedrock_server` (executable) is not found in `server_dir`.
        PermissionsError: If the `bedrock_server` executable is not marked as executable.
        SystemError: If creating the named pipe (FIFO) fails.
    """
    if not all([server_name, server_dir, config_dir]):
        raise MissingArgumentError(
            "server_name, server_dir, and config_dir are required."
        )

    logger.info(
        f"Starting server '{server_name}' in FOREGROUND blocking mode (Linux)..."
    )
    _foreground_server_shutdown_event.clear()

    # --- Pre-start Check ---
    # Verify no other instance of this server is running.
    if core_process.get_verified_bedrock_process(server_name, server_dir, config_dir):
        msg = f"Server '{server_name}' appears to be already running and verified. Aborting start."
        logger.warning(msg)
        raise ServerStartError(msg)
    else:
        # Clean up any stale PID file from a previous unclean shutdown.
        try:
            server_pid_file_path = core_process.get_bedrock_server_pid_file_path(
                server_name, config_dir
            )
            core_process.remove_pid_file_if_exists(server_pid_file_path)
            # Also clean up stale LAUNCHER PID file if this is a direct start
            launcher_pid_file_path = core_process.get_bedrock_launcher_pid_file_path(
                server_name, config_dir
            )
            core_process.remove_pid_file_if_exists(launcher_pid_file_path)
        except Exception as e:
            logger.warning(
                f"Could not clean up stale PID files for '{server_name}': {e}. Proceeding."
            )

    # --- Setup ---
    server_exe_path = os.path.join(server_dir, BEDROCK_EXECUTABLE_NAME)
    if not os.path.isfile(server_exe_path):
        raise AppFileNotFoundError(server_exe_path, "Server executable")
    if not os.access(server_exe_path, os.X_OK):
        raise PermissionsError(
            f"Server executable is not executable: {server_exe_path}"
        )

    output_file = os.path.join(server_dir, "server_output.txt")
    pipe_path = PIPE_NAME_TEMPLATE.format(server_name=re.sub(r"\W+", "_", server_name))

    # Setup OS signal handlers and the named pipe for communication.
    signal.signal(signal.SIGINT, _handle_os_signals)
    signal.signal(signal.SIGTERM, _handle_os_signals)
    try:
        if os.path.exists(pipe_path):
            os.remove(pipe_path)
        os.mkfifo(pipe_path, mode=0o600)
    except OSError as e:
        raise SystemError(f"Failed to create named pipe '{pipe_path}': {e}") from e

    bedrock_process: Optional[subprocess.Popen] = None
    server_stdout_handle = None
    main_pipe_listener_thread_obj: Optional[threading.Thread] = None

    try:
        # --- Launch Process ---
        # Redirect stdout/stderr to a log file.
        with open(output_file, "wb") as f:
            f.write(f"Starting Bedrock Server '{server_name}'...\n".encode("utf-8"))
        server_stdout_handle = open(output_file, "ab")

        # Launch the Bedrock server executable as a subprocess.
        bedrock_process = subprocess.Popen(
            [server_exe_path],
            cwd=server_dir,
            env={**os.environ, "LD_LIBRARY_PATH": "."},
            stdin=subprocess.PIPE,
            stdout=server_stdout_handle,
            stderr=subprocess.STDOUT,
            text=False,
            bufsize=0,
        )
        logger.info(
            f"Bedrock Server '{server_name}' started with PID: {bedrock_process.pid}."
        )

        # --- Manage PID and Pipe ---
        # Write the new process ID to the PID file.
        pid_file_path = core_process.get_bedrock_server_pid_file_path(
            server_name, config_dir
        )
        core_process.write_pid_to_file(pid_file_path, bedrock_process.pid)

        # Start the listener thread for the named pipe.
        main_pipe_listener_thread_obj = threading.Thread(
            target=_main_pipe_server_listener_thread,
            args=(
                pipe_path,
                bedrock_process,
                server_name,
                _foreground_server_shutdown_event,
            ),
            daemon=True,
        )
        main_pipe_listener_thread_obj.start()

        # --- Main Blocking Loop ---
        # This loop keeps the main thread alive, waiting for a shutdown signal.
        logger.info(
            f"Server '{server_name}' is running. Holding console. Press Ctrl+C to stop."
        )
        while (
            not _foreground_server_shutdown_event.is_set()
            and bedrock_process.poll() is None
        ):
            try:
                _foreground_server_shutdown_event.wait(timeout=1.0)
            except KeyboardInterrupt:
                _foreground_server_shutdown_event.set()

        # If the server process terminates on its own, trigger a shutdown.
        if bedrock_process.poll() is not None:
            logger.warning(
                f"Bedrock server '{server_name}' terminated unexpectedly. Shutting down."
            )
            _foreground_server_shutdown_event.set()

    except Exception as e_start:
        raise ServerStartError(
            f"Failed to start or manage server '{server_name}': {e_start}"
        ) from e_start
    finally:
        # --- Cleanup ---
        # This block ensures resources are cleaned up on shutdown.
        logger.info(f"Initiating cleanup for wrapper of '{server_name}'...")
        _foreground_server_shutdown_event.set()

        # Unblock the pipe listener thread so it can exit cleanly.
        try:
            with open(pipe_path, "w") as f:
                pass
        except OSError:
            pass
        if main_pipe_listener_thread_obj and main_pipe_listener_thread_obj.is_alive():
            main_pipe_listener_thread_obj.join(timeout=3.0)

        # Gracefully stop the Bedrock server process if it's still running.
        if bedrock_process and bedrock_process.poll() is None:
            logger.info(f"Sending 'stop' command to Bedrock server '{server_name}'.")
            try:
                if bedrock_process.stdin and not bedrock_process.stdin.closed:
                    bedrock_process.stdin.write(b"stop\n")
                    bedrock_process.stdin.flush()
                    bedrock_process.stdin.close()
                bedrock_process.wait(
                    timeout=settings.get("SERVER_STOP_TIMEOUT_SEC", 30)
                )
            except (subprocess.TimeoutExpired, OSError, ValueError):
                logger.warning(
                    f"Graceful stop failed for '{server_name}'. Terminating process."
                )
                core_process.terminate_process_by_pid(bedrock_process.pid)

        # Clean up the PID and pipe files.
        try:
            # Clean up SERVER PID file
            server_pid_file_path_final = core_process.get_bedrock_server_pid_file_path(
                server_name, config_dir
            )
            core_process.remove_pid_file_if_exists(server_pid_file_path_final)
        except Exception as e:
            logger.debug(f"Could not remove PID files during final cleanup: {e}")

        # Close file handles and reset signal handlers.
        if server_stdout_handle and not server_stdout_handle.closed:
            server_stdout_handle.close()

        signal.signal(signal.SIGINT, signal.SIG_DFL)
        signal.signal(signal.SIGTERM, signal.SIG_DFL)
        logger.info(f"Cleanup for server '{server_name}' finished.")


def _linux_send_command(server_name: str, command: str) -> None:
    """Sends a command to a running Bedrock server via its named pipe (FIFO) on Linux.

    This function attempts to open the FIFO specified by `server_name` (using
    :const:`.PIPE_NAME_TEMPLATE`) in write mode. If successful, it writes the
    `command` string (UTF-8 encoded, with a newline) to the FIFO. This command
    is then expected to be read by the :func:`._main_pipe_server_listener_thread`
    of the target server and forwarded to the Bedrock server's stdin.

    Args:
        server_name (str): The name of the server to send the command to.
        command (str): The command string to send (e.g., "list", "say Hello").

    Raises:
        MissingArgumentError: If `server_name` or `command` is empty.
        ServerNotRunningError: If the named pipe (FIFO) for the server does not
            exist or is disconnected (typically means the server or its pipe
            listener is not running).
        SendCommandError: If writing to the pipe fails for other ``OSError``
            reasons (e.g., permissions, disk full if pipe buffers to disk).
    """
    if not all([server_name, command]):
        raise MissingArgumentError("server_name and command cannot be empty.")

    pipe_path = PIPE_NAME_TEMPLATE.format(server_name=re.sub(r"\W+", "_", server_name))
    if not os.path.exists(pipe_path):
        raise ServerNotRunningError(
            f"Pipe '{pipe_path}' not found. Server likely not running."
        )

    try:
        with open(pipe_path, "w") as pipe_file:
            pipe_file.write(command + "\n")
            pipe_file.flush()
        logger.info(f"Sent command '{command}' to server '{server_name}'.")
    except (FileNotFoundError, BrokenPipeError) as e:
        raise ServerNotRunningError(
            f"Pipe '{pipe_path}' disconnected. Server likely not running."
        ) from e
    except OSError as e:
        raise SendCommandError(f"Failed to send command to '{pipe_path}': {e}") from e


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
