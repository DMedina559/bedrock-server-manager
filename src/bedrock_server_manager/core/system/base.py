# bedrock_server_manager/core/system/base.py
"""Provides base system utilities and foundational cross-platform functionalities.

This module contains a collection of essential system-level utilities that are
generally platform-agnostic or provide a common interface for operations that
might have platform-specific nuances handled elsewhere. It serves as a core
part of the system interaction layer.

Key functionalities include:

    - **Internet Connectivity**:
        - :func:`.check_internet_connectivity`: Verifies basic internet access.
    - **Filesystem Operations**:
        - :func:`.set_server_folder_permissions`: Sets appropriate permissions for
          server directories, with platform-aware logic.
        - :func:`.delete_path_robustly`: A utility for robustly deleting files
          or directories, handling potential read-only issues.
    - **Process Information**:
        - :func:`.is_server_running`: Checks if a Bedrock server process is active
          and verified, relying on :mod:`~.core.system.process`.
    - **Resource Monitoring**:
        - :class:`.ResourceMonitor`: A singleton class for monitoring CPU and
          memory usage of processes, requiring the ``psutil`` library.

Constants:
    - :const:`.PSUTIL_AVAILABLE`: Boolean indicating if ``psutil`` was imported,
      critical for :class:`.ResourceMonitor`.

Internal Helpers:
    - :func:`._handle_remove_readonly_onerror`: An error handler for ``shutil.rmtree``.
"""

import platform
import shutil
import logging
import socket
import stat
import threading
import os
import time
from datetime import timedelta
from typing import Optional, Dict, Any, Tuple

# Third-party imports. psutil is optional but required for process monitoring.
try:
    import psutil

    PSUTIL_AVAILABLE = True
    """bool: ``True`` if the `psutil` library was successfully imported, ``False`` otherwise.
    This flag is checked by components like :class:`.ResourceMonitor` to determine
    if process resource monitoring capabilities are available.
    """
except ImportError:
    PSUTIL_AVAILABLE = False
    # Ensure PSUTIL_AVAILABLE is defined even if import fails for linters/type checkers.
    # The docstring above is associated with the True assignment by Sphinx.

# Local application imports.
from bedrock_server_manager.core.system import process as core_process
from bedrock_server_manager.error import (
    PermissionsError,
    AppFileNotFoundError,
    MissingArgumentError,
    CommandNotFoundError,
    ServerProcessError,
    SystemError,
    InternetConnectivityError,
    FileOperationError,
)

logger = logging.getLogger(__name__)


def check_internet_connectivity(
    host: str = "8.8.8.8", port: int = 53, timeout: int = 3
) -> None:
    """Checks for basic internet connectivity by attempting a TCP socket connection.

    This function tries to establish a TCP connection to a specified `host` and
    `port` with a given `timeout`. Success indicates likely internet access.
    Failure (timeout or other ``OSError``) raises an
    :class:`~bedrock_server_manager.error.InternetConnectivityError`.

    Args:
        host (str, optional): The hostname or IP address to connect to.
            Defaults to "8.8.8.8" (Google Public DNS).
        port (int, optional): The port number to connect to.
            Defaults to 53 (DNS port).
        timeout (int, optional): The connection timeout in seconds.
            Defaults to 3.

    Raises:
        InternetConnectivityError: If the socket connection fails due to a
            timeout, ``OSError`` (e.g., network unreachable, host not found),
            or any other unexpected exception during the check.
    """
    logger.debug(
        f"Checking internet connectivity by attempting connection to {host}:{port}..."
    )
    try:
        # Attempt to create a socket connection to a reliable external host.
        socket.create_connection((host, port), timeout=timeout).close()
        logger.debug("Internet connectivity check successful.")
    except socket.timeout:
        error_msg = f"Connectivity check failed: Connection to {host}:{port} timed out after {timeout} seconds."
        logger.error(error_msg)
        raise InternetConnectivityError(error_msg) from None
    except OSError as ex:
        error_msg = (
            f"Connectivity check failed: Cannot connect to {host}:{port}. Error: {ex}"
        )
        logger.error(error_msg)
        raise InternetConnectivityError(error_msg) from ex
    except Exception as e:
        error_msg = f"An unexpected error occurred during connectivity check: {e}"
        logger.error(error_msg, exc_info=True)
        raise InternetConnectivityError(error_msg) from e


def set_server_folder_permissions(server_dir: str) -> None:
    """Sets appropriate permissions for a Bedrock server installation directory.

    This function adjusts permissions recursively for the specified `server_dir`
    based on the operating system:

        -   **On Linux**:

            -   Ownership of all files and directories is set to the current effective
                user (UID) and group (GID) using ``os.chown``.
            -   Directories are set to ``0o775`` (rwxrwxr-x).
            -   The main server executable (assumed to be named "bedrock_server") is
                set to ``0o775`` (rwxrwxr-x).
            -   Other files are set to ``0o664`` (rw-rw-r--).

        -   **On Windows**:

            -   Ensures that the "write" permission (``stat.S_IWRITE`` or ``stat.S_IWUSR``)
                is set for all files and directories. It preserves other existing
                permissions by ORing with the current mode.

        -   **Other OS**:

            -   Logs a warning that permission setting is not implemented.

    Args:
        server_dir (str): The absolute path to the server's installation directory.

    Raises:
        MissingArgumentError: If `server_dir` is empty or not a string.
        AppFileNotFoundError: If `server_dir` does not exist or is not a directory.
        PermissionsError: If any ``OSError`` occurs during `os.chown` or `os.chmod`
            operations (e.g., due to insufficient privileges to change ownership
            or permissions), or for other unexpected errors.
    """
    if not isinstance(server_dir, str) or not server_dir:
        raise MissingArgumentError(
            "Server directory cannot be empty and must be a string."
        )
    if not os.path.isdir(server_dir):
        raise AppFileNotFoundError(server_dir, "Server directory")

    os_name = platform.system()
    logger.debug(
        f"Setting permissions for server directory: {server_dir} (OS: {os_name})"
    )

    try:
        if os_name == "Linux":
            current_uid = os.geteuid()
            current_gid = os.getegid()
            logger.debug(f"Setting ownership to UID={current_uid}, GID={current_gid}")

            for root, dirs, files in os.walk(server_dir, topdown=True):
                for d in dirs:
                    dir_path = os.path.join(root, d)
                    os.chown(dir_path, current_uid, current_gid)
                    os.chmod(dir_path, 0o775)
                for f in files:
                    file_path = os.path.join(root, f)
                    os.chown(file_path, current_uid, current_gid)
                    # The main executable needs execute permissions.
                    if os.path.basename(file_path) == "bedrock_server":
                        os.chmod(file_path, 0o775)
                    else:
                        os.chmod(file_path, 0o664)
            # Set top-level permissions last.
            os.chown(server_dir, current_uid, current_gid)
            os.chmod(server_dir, 0o775)
            logger.info(f"Successfully set Linux permissions for: {server_dir}")

        elif os_name == "Windows":
            logger.debug("Ensuring write permissions (S_IWRITE) on Windows...")
            for root, dirs, files in os.walk(server_dir):
                for name in dirs + files:
                    path = os.path.join(root, name)
                    try:
                        current_mode = os.stat(path).st_mode
                        os.chmod(path, current_mode | stat.S_IWRITE | stat.S_IWUSR)
                    except OSError as e_chmod:
                        logger.warning(
                            f"Could not set write permission on '{path}': {e_chmod}"
                        )
            logger.info(
                f"Successfully ensured write permissions for: {server_dir} on Windows"
            )
        else:
            logger.warning(f"Permission setting not implemented for OS: {os_name}")

    except OSError as e:
        raise PermissionsError(
            f"Failed to set permissions for '{server_dir}': {e}"
        ) from e
    except Exception as e:
        raise PermissionsError(f"Unexpected error during permission setup: {e}") from e


def is_server_running(server_name: str, server_dir: str, config_dir: str) -> bool:
    """Checks if a specific Bedrock server process is running and verified.

    This function acts as a high-level convenience wrapper around
    :func:`~.core.system.process.get_verified_bedrock_process`. It determines
    if a Bedrock server, identified by `server_name`, is active by checking
    its PID file and verifying the running process's identity (e.g., executable
    path and CWD).

    Args:
        server_name (str): The unique name of the server instance.
        server_dir (str): The server's installation directory, used for
            process verification.
        config_dir (str): The main application configuration directory where the
            server's PID file is expected to be located.

    Returns:
        bool: ``True`` if a matching and verified Bedrock server process is found
        to be running, ``False`` otherwise (e.g., if ``psutil`` is unavailable,
        PID file is missing, process is not running, or verification fails).

    Raises:
        MissingArgumentError: If `server_name`, `server_dir`, or `config_dir`
            are empty or not strings.
    """
    if not isinstance(server_name, str) or not server_name:
        raise MissingArgumentError("server_name cannot be empty and must be a string.")
    if not isinstance(server_dir, str) or not server_dir:
        raise MissingArgumentError("server_dir cannot be empty and must be a string.")
    if not isinstance(config_dir, str) or not config_dir:
        raise MissingArgumentError("config_dir cannot be empty and must be a string.")

    # get_verified_bedrock_process handles logging for most non-critical failures
    # and returns None in those cases.
    return (
        core_process.get_verified_bedrock_process(server_name, server_dir, config_dir)
        is not None
    )


def _handle_remove_readonly_onerror(func, path, exc_info):
    """Error handler for ``shutil.rmtree`` to manage read-only files, primarily on Windows.

    This function is designed to be passed as the `onerror` argument to
    ``shutil.rmtree``. When ``shutil.rmtree`` encounters an ``OSError`` (often
    a ``PermissionError`` on Windows) while trying to delete a file, this handler
    is called.

    It checks if the error is due to the file at `path` being read-only.
    If so, it attempts to make the file writable (``stat.S_IWUSR | stat.S_IWRITE``)
    and then retries the original operation that failed (e.g., `os.remove` or
    `os.rmdir`), which is passed as the `func` argument.

    If the error is not related to read-only status, or if making the file
    writable fails, the original exception (from `exc_info`) is re-raised.

    Args:
        func (Callable): The function that raised the exception (e.g., `os.remove`).
        path (str): The path to the file or directory that caused the error.
        exc_info (Tuple): A tuple as returned by ``sys.exc_info()``, containing
            the exception type, value, and traceback.
    """
    # Check if the exception is an OSError and related to permissions
    # The specific error codes for read-only might vary, but AccessDenied (EACCES) is common.
    # We primarily check if we can make it writable.
    if isinstance(exc_info[1], OSError) and not os.access(path, os.W_OK):
        logger.debug(
            f"Read-only error on path '{path}'. Attempting to make it writable and retry."
        )
        try:
            os.chmod(path, stat.S_IWUSR | stat.S_IWRITE)
            func(path)  # Retry the original function (e.g., os.remove or os.rmdir)
        except Exception as e_retry:
            logger.warning(
                f"Failed to make '{path}' writable and retry operation '{func.__name__}': {e_retry}. Original error: {exc_info[1]}"
            )
            # Re-raise the original exception if retry fails
            raise exc_info[1] from e_retry
    else:
        # If it's not an OSError we can handle or not a writable issue, re-raise the original exception.
        # For example, if the path is a directory that's not empty and func is os.rmdir.
        logger.debug(
            f"Unhandled error during rmtree: {exc_info[1]} on path {path}. Re-raising."
        )
        raise exc_info[1]


def delete_path_robustly(path_to_delete: str, item_description: str) -> bool:
    """Deletes a file or directory robustly, attempting to handle read-only attributes.

    This function attempts to delete the specified `path_to_delete`.

        - If it's a directory, it uses `shutil.rmtree` with a custom error
          handler (:func:`._handle_remove_readonly_onerror`) that tries to make
          read-only files writable before retrying deletion.
        - If it's a file, it first checks if it's writable. If not, it attempts
          to make it writable (``stat.S_IWRITE | stat.S_IWUSR``) before calling `os.remove`.
        - If the path does not exist, it logs this and returns ``True``.
        - If the path is neither a file nor a directory, it logs a warning and returns ``False``.

    Deletion failures are logged, and the function returns ``False`` in such cases.

    Args:
        path_to_delete (str): The absolute path to the file or directory to delete.
        item_description (str): A human-readable description of the item being
            deleted, used for logging messages (e.g., "temporary file",
            "old backup directory").

    Returns:
        bool: ``True`` if the deletion was successful or if the path did not
        exist initially. ``False`` if an error occurred during deletion or if
        the path was neither a file nor a directory.

    Raises:
        MissingArgumentError: If `path_to_delete` or `item_description` are
            empty or not strings.
    """
    if not isinstance(path_to_delete, str) or not path_to_delete:
        raise MissingArgumentError("path_to_delete cannot be empty.")
    if not isinstance(item_description, str) or not item_description:
        raise MissingArgumentError("item_description cannot be empty.")

    if not os.path.exists(path_to_delete):
        logger.debug(
            f"{item_description.capitalize()} at '{path_to_delete}' not found, skipping."
        )
        return True

    logger.info(f"Preparing to delete {item_description}: {path_to_delete}")
    try:
        if os.path.isdir(path_to_delete):
            # Use the custom error handler for directories.
            shutil.rmtree(path_to_delete, onerror=_handle_remove_readonly_onerror)
            logger.info(
                f"Successfully deleted {item_description} directory: {path_to_delete}"
            )
        elif os.path.isfile(path_to_delete):
            # For single files, manually check and set permissions if needed.
            if not os.access(path_to_delete, os.W_OK):
                os.chmod(path_to_delete, stat.S_IWRITE | stat.S_IWUSR)
            os.remove(path_to_delete)
            logger.info(
                f"Successfully deleted {item_description} file: {path_to_delete}"
            )
        else:
            logger.warning(
                f"Path '{path_to_delete}' is not a file or directory. Skipping."
            )
            return False
        return True
    except Exception as e:
        logger.error(
            f"Failed to delete {item_description} at '{path_to_delete}': {e}",
            exc_info=True,
        )
        return False


# --- RESOURCE MONITOR ---
class ResourceMonitor:
    """A singleton class for monitoring process resource usage (CPU, memory, uptime).

    This class provides a way to get resource statistics for a given ``psutil.Process``
    object. It is implemented as a thread-safe singleton to ensure that the
    internal state required for calculating CPU percentage (which relies on
    comparing CPU times between calls) is maintained consistently across the
    application for each monitored process.

    The monitor stores the last CPU times and timestamp on a per-PID basis
    to correctly calculate CPU utilization for individual processes.

    Requires the ``psutil`` library. If ``psutil`` is not available (indicated by
    :const:`.PSUTIL_AVAILABLE` being ``False``), methods like :meth:`.get_stats`
    will typically log a warning and return ``None`` or raise an error.

    Attributes:
        _instance (Optional[ResourceMonitor]): The single instance of this class.
        _lock (threading.Lock): A lock to ensure thread-safe singleton creation
            and initialization.
        _last_readings (Dict[int, Tuple[Any, float]]): A dictionary storing the
            last CPU times (``psutil.cpu_times`` result) and timestamp for each
            monitored PID. Keyed by PID.
        _initialized (bool): A flag to ensure ``__init__`` logic runs only once.
    """

    _instance: Optional["ResourceMonitor"] = None
    _lock = threading.Lock()

    def __new__(cls, *args: Any, **kwargs: Any) -> "ResourceMonitor":
        """Ensures that only one instance of ResourceMonitor is created (Singleton pattern)."""
        if cls._instance is None:
            with cls._lock:
                # Double-check locking
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initializes the resource monitor's state.

        This constructor is called only once for the singleton instance.
        It sets up the `_last_readings` dictionary to store CPU time snapshots
        for different processes and an `_initialized` flag.
        """
        if not hasattr(self, "_initialized"):  # Ensure this runs only once
            with self._lock:
                if not hasattr(self, "_initialized"):
                    self._last_readings: Dict[int, Tuple[Any, float]] = {}
                    self._initialized: bool = True

    def get_stats(self, process: "psutil.Process") -> Optional[Dict[str, Any]]:
        """Calculates and returns resource usage statistics for the given process.

        If ``psutil`` is not available, this method logs a warning and returns ``None``.

        The CPU percentage is calculated based on the change in CPU times since
        the last call for the same process ID (PID). The first call for a PID
        will report 0% CPU usage as there's no prior data for comparison.

        Args:
            process (psutil.Process): An instance of ``psutil.Process`` representing
                the process to monitor.

        Returns:
            Optional[Dict[str, Any]]: A dictionary containing the statistics if
            successful, or ``None`` if ``psutil`` is unavailable or the process
            is inaccessible (e.g., ``psutil.NoSuchProcess``, ``psutil.AccessDenied``).
            The dictionary structure is:
            ::

                {
                    "pid": int,          # Process ID
                    "cpu_percent": float, # CPU usage percentage (e.g., 12.3)
                    "memory_mb": float,  # Resident Set Size (RSS) memory in megabytes
                    "uptime": str        # Process uptime formatted as "HH:MM:SS"
                }

        Raises:
            TypeError: If the input `process` is not a ``psutil.Process`` instance.
            SystemError: If an unexpected error occurs while fetching stats using ``psutil``
                         (other than ``NoSuchProcess`` or ``AccessDenied``).
        """
        if not PSUTIL_AVAILABLE:
            logger.warning(
                "psutil is not available. Cannot get process stats for PID %s.",
                getattr(process, "pid", "N/A"),  # Safely get PID for log if possible
            )
            return None

        # Ensure psutil is available before using psutil.Process in isinstance
        if PSUTIL_AVAILABLE and not isinstance(process, psutil.Process):
            raise TypeError(
                f"Input must be a valid psutil.Process object, got {type(process).__name__}."
            )

        pid = process.pid
        try:
            with process.oneshot():  # Efficiently get multiple process infos
                current_cpu_times = (
                    process.cpu_times()
                )  # specific type: psutil._common.scpustats
                current_timestamp = time.time()
                cpu_percent = 0.0

                if pid in self._last_readings:
                    prev_cpu_times, prev_timestamp = self._last_readings[pid]
                    time_delta = current_timestamp - prev_timestamp

                    if time_delta > 0.01:  # Avoid division by zero or tiny intervals
                        # Sum of user and system time deltas
                        process_cpu_time_delta = (
                            current_cpu_times.user - prev_cpu_times.user
                        ) + (current_cpu_times.system - prev_cpu_times.system)
                        # Normalize by number of CPU cores for system-wide percentage
                        cpu_count = psutil.cpu_count(logical=True) or 1
                        cpu_percent = (
                            (process_cpu_time_delta / time_delta) * 100 / cpu_count
                        )
                        cpu_percent = max(0.0, cpu_percent)  # Ensure non-negative

                self._last_readings[pid] = (current_cpu_times, current_timestamp)

                memory_info = (
                    process.memory_info()
                )  # specific type: psutil._common.smeninfo
                memory_mb = memory_info.rss / (1024 * 1024)  # RSS in MB

                create_time = process.create_time()  # timestamp
                uptime_seconds = current_timestamp - create_time
                uptime_str = str(timedelta(seconds=int(uptime_seconds)))

                return {
                    "pid": pid,
                    "cpu_percent": round(cpu_percent, 1),
                    "memory_mb": round(memory_mb, 1),
                    "uptime": uptime_str,
                }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            # If process disappears or access is denied, remove its last reading
            if pid in self._last_readings:
                del self._last_readings[pid]
            logger.debug(
                f"Could not get stats for PID {pid}: Process gone or access denied."
            )
            return None
        except Exception as e:
            # Catch any other psutil errors or unexpected issues
            raise SystemError(f"Failed to get stats for PID {pid}: {e}") from e
