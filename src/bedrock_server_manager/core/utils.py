# bedrock_server_manager/core/utils.py
"""
Provides low-level core utility functions for server management.

This module contains a collection of helper functions that perform specific,
atomic tasks related to server management. These utilities are designed to be
used by higher-level components like the :class:`~.core.bedrock_server.BedrockServer`
or API endpoints.

Key functions include:
- :func:`core_validate_server_name_format`: Validates server names against a regex.
- :func:`core_execute_screen_attach`: A Linux-specific utility to attach to a
  ``screen`` session.

.. warning::
    The functions :func:`check_server_status` and :func:`update_server_status_in_config`
    are currently **unused** in the application. They represent a legacy method of
    determining server status by parsing log files, which has been superseded by
    more reliable process-based checks (e.g., using ``psutil``). They are retained
    for potential future reference or alternative implementations but should not be
    relied upon in their current state.
"""

import os
import re
import logging
import platform
import subprocess
import time
import shutil
from typing import Tuple, Optional

# Local imports
from bedrock_server_manager.error import (
    MissingArgumentError,
    FileOperationError,
    InvalidServerNameError,
    SystemError,
    CommandNotFoundError,
)

# Dummy import for unused legacy functions.
# This would need to be a real import for the unused functions to work.
core_server_utils = None

logger = logging.getLogger(__name__)


# --- Server Stuff ---


def core_validate_server_name_format(server_name: str) -> None:
    """
    Validates the format of a server name against a specific pattern.

    The function checks that the server name is not empty and contains only
    alphanumeric characters (a-z, A-Z, 0-9), hyphens (-), and underscores (_).
    This helps prevent issues with file paths and system commands.

    Args:
        server_name (str): The server name string to validate.

    Raises:
        :class:`~.error.InvalidServerNameError`: If the server name is empty or
            contains invalid characters.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    if not re.fullmatch(r"^[a-zA-Z0-9_-]+$", server_name):
        raise InvalidServerNameError(
            "Invalid server name format. Only use letters (a-z, A-Z), "
            "numbers (0-9), hyphens (-), and underscores (_)."
        )
    logger.debug(f"Server name '{server_name}' format is valid.")


# --- Currently Unused ---
def check_server_status(
    server_name: str,
    base_dir: str,
    max_attempts: int = 10,
    chunk_size_bytes: int = 8192,
    max_scan_bytes: int = 1 * 1024 * 1024,
) -> str:
    """
    Determines a server's status by reading the end of its log file.

    .. warning::
        This function is currently unused and represents a legacy approach.
        Modern status checks rely on process monitoring, which is more reliable
        than log parsing.

    This method efficiently reads the server's log file (``server_output.txt``)
    backwards in chunks to find the most recent status indicator, such as
    "Server started." or "Quit correctly.". It includes a brief wait period
    to allow the log file to be created if it doesn't exist.

    Args:
        server_name (str): The name of the server.
        base_dir (str): The base directory containing all server installations.
        max_attempts (int): The maximum number of attempts to wait for the log
            file to appear, with a 0.5-second sleep between attempts.
        chunk_size_bytes (int): The size of each chunk to read from the end of
            the file.
        max_scan_bytes (int): The maximum total bytes to scan backwards from
            the end of the file before giving up.

    Returns:
        str: The determined server status. Possible values are "RUNNING",
        "STARTING", "RESTARTING", "STOPPING", "STOPPED", or "UNKNOWN".

    Raises:
        :class:`~.error.MissingArgumentError`: If ``server_name`` or ``base_dir`` is empty.
        :class:`~.error.FileOperationError`: If reading the log file fails due to
            an OS-level error (e.g., permissions).
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    if not base_dir:
        raise MissingArgumentError("Base directory cannot be empty.")

    log_file_path = os.path.join(base_dir, server_name, "server_output.txt")
    status = "UNKNOWN"  # Default status

    logger.info(
        f"Checking server status for '{server_name}' by reading log file: {log_file_path}"
    )

    # --- Wait for log file existence ---
    attempt = 0
    sleep_interval = 0.5
    while not os.path.exists(log_file_path) and attempt < max_attempts:
        logger.debug(
            f"Log file '{log_file_path}' not found. Waiting... (Attempt {attempt + 1}/{max_attempts})"
        )
        time.sleep(sleep_interval)
        attempt += 1

    if not os.path.exists(log_file_path):
        logger.warning(
            f"Log file '{log_file_path}' did not appear within {max_attempts * sleep_interval} seconds."
        )
        return "UNKNOWN"

    # --- Read log file efficiently from the end ---
    try:
        with open(log_file_path, "rb") as f:  # Open in binary mode for seeking
            f.seek(0, os.SEEK_END)
            file_size = f.tell()
            bytes_scanned = 0
            buffer = b""

            while bytes_scanned < max_scan_bytes and bytes_scanned < file_size:
                read_size = min(chunk_size_bytes, file_size - bytes_scanned)
                f.seek(file_size - bytes_scanned - read_size)
                chunk = f.read(read_size)
                bytes_scanned += read_size
                buffer = chunk + buffer

                lines = buffer.decode("utf-8", errors="ignore").splitlines()

                for line in reversed(lines):
                    line = line.strip()
                    if not line:
                        continue

                    if "Server started." in line:
                        status = "RUNNING"
                        break
                    elif "Starting Server" in line:
                        status = "STARTING"
                        break
                    elif "Restarting server in 10 seconds" in line:
                        status = "RESTARTING"
                        break
                    elif "Shutting down server in 10 seconds" in line:
                        status = "STOPPING"
                        break
                    elif "Quit correctly." in line:
                        status = "STOPPED"
                        break

                if status != "UNKNOWN":
                    logger.debug(f"Status '{status}' determined from log content.")
                    break

                if (
                    not buffer.startswith(b"\n")
                    and not buffer.startswith(b"\r")
                    and bytes_scanned < file_size
                ):
                    last_newline = max(buffer.rfind(b"\n"), buffer.rfind(b"\r"))
                    if last_newline != -1:
                        buffer = buffer[: last_newline + 1]

            if status == "UNKNOWN":
                logger.warning(
                    f"Could not determine server status after scanning last {bytes_scanned} bytes of log file '{log_file_path}'."
                )

    except OSError as e:
        logger.error(
            f"Failed to read server log file '{log_file_path}': {e}", exc_info=True
        )
        raise FileOperationError(
            f"Failed to read server log '{log_file_path}': {e}"
        ) from e
    except Exception as e:
        logger.error(
            f"Unexpected error processing log file '{log_file_path}': {e}",
            exc_info=True,
        )
        return "UNKNOWN"

    logger.info(
        f"Determined status for server '{server_name}': {status} (from log check)"
    )
    return status


def update_server_status_in_config(
    server_name: str, base_dir: str, config_dir: Optional[str] = None
) -> None:
    """
    Updates a server's status in its config file based on a log check.

    .. warning::
        This function is currently unused and not functional in its current
        state, as it depends on :func:`check_server_status` and a dummy
        ``core_server_utils`` import.

    This function calls :func:`check_server_status` to get the current status
    and compares it to the last known status in the server's configuration.
    If the status has changed and is informative (i.e., not "UNKNOWN"), it
    writes the new status to the configuration file.

    Args:
        server_name (str): The name of the server.
        base_dir (str): The base directory containing the server's folder, used
            to locate the log file.
        config_dir (Optional[str]): The base directory containing server config
            folders. If ``None``, the application's default config directory
            would be used.

    Raises:
        :class:`~.error.MissingArgumentError`: If ``server_name`` or ``base_dir`` is empty.
        :class:`~.error.InvalidServerNameError`: If ``server_name`` has an invalid format.
        :class:`~.error.FileOperationError`: If reading the log or reading/writing
            the config file fails.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    if not base_dir:
        raise MissingArgumentError("Base directory cannot be empty.")

    logger.debug(
        f"Updating status in config for server '{server_name}' based on log check."
    )

    try:
        checked_status = check_server_status(server_name, base_dir)
        # The following lines are non-functional due to dummy import
        current_config_status = core_server_utils.get_server_status_from_config(
            server_name, config_dir
        )

        logger.debug(
            f"Server '{server_name}': Status from log='{checked_status}', Status from config='{current_config_status}'"
        )

        if checked_status != current_config_status and checked_status != "UNKNOWN":
            logger.info(
                f"Status mismatch for '{server_name}'. Updating config from '{current_config_status}' to '{checked_status}'."
            )
            core_server_utils.manage_server_config(
                server_name=server_name,
                key="status",
                operation="write",
                value=checked_status,
                config_dir=config_dir,
            )
            logger.info(
                f"Successfully updated server status for '{server_name}' to '{checked_status}'."
            )
        else:
            logger.debug(
                f"Server '{server_name}' status ('{checked_status}') matches config or is UNKNOWN. No update needed."
            )

    except (FileOperationError, MissingArgumentError, InvalidServerNameError) as e:
        logger.error(
            f"Failed to update server status in config for '{server_name}': {e}",
            exc_info=True,
        )
        raise
    except Exception as e:
        logger.error(
            f"Unexpected error updating server status in config for '{server_name}': {e}",
            exc_info=True,
        )
        raise FileOperationError(
            f"Unexpected error updating server status config for '{server_name}': {e}"
        ) from e


# --- Screen Attach ---
def core_execute_screen_attach(screen_session_name: str) -> Tuple[bool, str]:
    """
    Executes the command to attach to a Linux ``screen`` session (Linux-specific).

    This function is a wrapper around the ``screen -r <session_name>`` command.
    It checks if the ``screen`` utility is installed and handles common outcomes,
    such as the session not being found.

    Args:
        screen_session_name (str): The name of the screen session to attach to
            (e.g., "bedrock-servername").

    Returns:
        Tuple[bool, str]: A tuple where the first element is a boolean
        indicating success, and the second is a string containing a descriptive
        message or error details.

    Raises:
        :class:`~.error.SystemError`: If the function is called on an operating
            system other than Linux.
        :class:`~.error.CommandNotFoundError`: If the ``screen`` command is not
            found in the system's PATH.
    """
    if platform.system() != "Linux":
        raise SystemError("Screen session attachment is only supported on Linux.")

    screen_cmd = shutil.which("screen")
    if not screen_cmd:
        raise CommandNotFoundError(
            "screen", "'screen' command not found. Is the 'screen' package installed?"
        )

    command = [screen_cmd, "-r", screen_session_name]
    logger.debug(f"Executing screen attach command: {' '.join(command)}")
    try:
        # This function only triggers the command; actual interaction happens
        # in the user's terminal, not through this process's I/O.
        process = subprocess.run(
            command, check=True, capture_output=True, text=True, timeout=10
        )
        output = process.stdout.strip() + (
            ("\n" + process.stderr.strip()) if process.stderr.strip() else ""
        )
        logger.info(
            f"Screen attach command executed for '{screen_session_name}'. Output: {output}"
        )
        return (
            True,
            f"Attach command executed for session '{screen_session_name}'.",
        )
    except subprocess.CalledProcessError as e:
        stderr_lower = (e.stderr or "").lower()
        if (
            "no screen session found" in stderr_lower
            or "there is no screen to be resumed" in stderr_lower
        ):
            msg = f"Screen session '{screen_session_name}' not found."
            logger.warning(msg)
            return False, msg
        else:
            msg = f"Failed to attach to screen '{screen_session_name}'. Error: {e.stderr or 'Unknown error'}"
            logger.error(msg, exc_info=True)
            return False, msg
    except subprocess.TimeoutExpired:
        msg = (
            f"Timeout while trying to attach to screen session '{screen_session_name}'."
        )
        logger.error(msg)
        return False, msg
    except FileNotFoundError:  # Safeguard; should be caught by shutil.which
        raise CommandNotFoundError(
            "screen",
            message="'screen' command not found unexpectedly during execution.",
        )