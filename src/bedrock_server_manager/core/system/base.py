# bedrock_server_manager/core/system/base.py
"""Shared filesystem, connectivity, permission and resource utilities."""

import asyncio
import logging
import os
import platform
import shutil
import stat
import threading
import time
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import aiofiles
import aiofiles.os
import aiofiles.ospath
import aiohttp

from ...utils.threads import run_in_thread

try:
    import psutil

    PSUTIL_AVAILABLE = True
    """bool: ``True`` if the `psutil` library was successfully imported, ``False`` otherwise.
    This flag is checked by components like :class:`.ProcessResourceMonitor` to determine
    if process resource monitoring capabilities are available.
    """
except ImportError:
    PSUTIL_AVAILABLE = False
    # Ensure PSUTIL_AVAILABLE is defined even if import fails for linters/type checkers.
    # The docstring above is associated with the True assignment by Sphinx.

from ...error import (
    AppFileNotFoundError,
    InternetConnectivityError,
    MissingArgumentError,
    PermissionsError,
    SystemError,
)
from ...logging import log_operation_error
from . import process as core_process

logger = logging.getLogger(__name__)


async def find_files(
    directory: str,
    pattern: str = "*",
    sort_by: str = "name",
    reverse: bool = False,
    include_metadata: bool = False,
) -> Union[List[str], List[Dict[str, Any]]]:
    """Find sorted files matching a glob and return paths or metadata.

    Metadata contains path, name, size and modification time.
    """

    def _find() -> Union[List[str], List[Dict[str, Any]]]:
        dir_path = Path(directory)
        if not dir_path.is_dir():
            return []

        files = [p for p in dir_path.glob(pattern) if p.is_file()]

        if sort_by == "mtime":
            files.sort(key=lambda p: p.stat().st_mtime, reverse=reverse)
        elif sort_by == "size":
            files.sort(key=lambda p: p.stat().st_size, reverse=reverse)
        else:  # default to "name"
            files.sort(key=lambda p: p.name, reverse=reverse)

        if include_metadata:
            return [
                {
                    "path": str(p),
                    "name": p.name,
                    "size": p.stat().st_size,
                    "mtime": p.stat().st_mtime,
                }
                for p in files
            ]
        else:
            return [str(p) for p in files]

    return await run_in_thread(_find)


def can_manage_services() -> bool:
    """Indicates if a system service manager (``systemctl`` or ``sc.exe``) is available.

    If ``True``, features related to managing system services (for the Web UI or game servers)
    can be expected to work.
    """
    os_name = platform.system()
    if os_name == "Linux":
        return shutil.which("systemctl") is not None
    elif os_name == "Windows":
        return shutil.which("sc.exe") is not None
    return False


async def check_internet_connectivity(
    url: str = "http://clients3.google.com/generate_204", timeout: int = 3
) -> None:
    """Probe an HTTP URL within the timeout in seconds.

    Raise ``InternetConnectivityError`` when the probe fails.
    """
    logger.debug("Checking internet connectivity by attempting HTTP GET to %s...", url)
    try:
        timeout_client = aiohttp.ClientTimeout(total=timeout)
        async with aiohttp.ClientSession(timeout=timeout_client) as session:
            async with session.get(url) as response:
                if 200 <= response.status < 300:
                    logger.debug("Asynchronous internet connectivity check successful.")
                else:
                    error_msg = f"Connectivity check failed: HTTP status {response.status} from {url}."
                    logger.error(error_msg)
                    raise InternetConnectivityError(error_msg)
    except asyncio.TimeoutError:
        error_msg = f"Connectivity check failed: Connection to {url} timed out after {timeout} seconds."
        logger.error(error_msg)
        raise InternetConnectivityError(error_msg) from None
    except aiohttp.ClientError as ex:
        error_msg = f"Connectivity check failed: Cannot connect to {url}. Error: {ex}"
        log_operation_error(logger, error_msg, error=ex)
        raise InternetConnectivityError(error_msg) from ex


async def set_server_folder_permissions(server_dir: str) -> None:  # noqa: C901
    """Apply server-directory ownership and writable/executable permissions.

    Linux uses modes 0775 for directories/executables and 0664 for other files;
    Windows preserves existing modes while adding write permission.
    """
    if not isinstance(server_dir, str) or not server_dir:
        raise MissingArgumentError(
            "Server directory cannot be empty and must be a string."
        )
    if not await aiofiles.ospath.isdir(server_dir):
        raise AppFileNotFoundError(server_dir, "Server directory")

    os_name = platform.system()
    logger.debug(
        "Setting permissions for server directory: %s (OS: %s)", server_dir, os_name
    )

    def _set_perms() -> None:
        try:
            if os_name == "Linux":
                current_uid = os.geteuid()  # type: ignore[attr-defined]
                current_gid = os.getegid()  # type: ignore[attr-defined]
                logger.debug(
                    "Setting ownership to UID=%s, GID=%s", current_uid, current_gid
                )

                for root, dirs, files in os.walk(server_dir, topdown=True):
                    for d in dirs:
                        dir_path = os.path.join(root, d)
                        os.chown(dir_path, current_uid, current_gid)  # type: ignore[attr-defined]
                        os.chmod(dir_path, 0o775)
                    for f in files:
                        file_path = os.path.join(root, f)
                        os.chown(file_path, current_uid, current_gid)  # type: ignore[attr-defined]
                        # The main executable needs execute permissions.
                        if os.path.basename(file_path) == "bedrock_server":
                            os.chmod(file_path, 0o775)
                        else:
                            os.chmod(file_path, 0o664)
                # Set top-level permissions last.
                os.chown(server_dir, current_uid, current_gid)  # type: ignore[attr-defined]
                os.chmod(server_dir, 0o775)
                logger.debug("Successfully set Linux permissions for: %s", server_dir)

            elif os_name == "Windows":
                logger.debug("Ensuring write permissions (S_IWRITE) on Windows...")
                failures: list[OSError] = []
                for root, dirs, files in os.walk(server_dir):
                    for name in dirs + files:
                        path = os.path.join(root, name)
                        try:
                            current_mode = os.stat(path).st_mode
                            os.chmod(path, current_mode | stat.S_IWRITE | stat.S_IWUSR)
                        except OSError as e_chmod:
                            failures.append(e_chmod)
                            logger.warning(
                                "Could not set write permission on '%s': %s",
                                path,
                                e_chmod,
                            )
                if failures:
                    raise PermissionsError(
                        f"Failed to set write permissions on {len(failures)} paths."
                    ) from failures[0]
                logger.debug(
                    "Successfully ensured write permissions for: %s on Windows",
                    server_dir,
                )
            else:
                logger.warning("Permission setting not implemented for OS: %s", os_name)

        except PermissionsError:
            raise
        except OSError as e:
            raise PermissionsError(
                f"Failed to set permissions for '{server_dir}': {e}"
            ) from e
        except Exception as e:
            raise PermissionsError(
                f"Unexpected error during permission setup: {e}"
            ) from e

    await run_in_thread(_set_perms)


async def is_server_running(server_name: str, server_dir: str, config_dir: str) -> bool:
    """Asynchronously checks if a specific Bedrock server process is running and verified.

    This acts as a high-level convenience wrapper around
    :func:`~.core.system.process.get_verified_bedrock_process`.
    """
    if not isinstance(server_name, str) or not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    if not isinstance(server_dir, str) or not server_dir:
        raise MissingArgumentError("Server directory cannot be empty.")
    if not isinstance(config_dir, str) or not config_dir:
        raise MissingArgumentError("Configuration directory cannot be empty.")

    process = await core_process.get_verified_bedrock_process(
        server_name, server_dir, config_dir
    )
    return process is not None


def _handle_remove_readonly_onerror(func, path, exc_info):
    """Make a read-only path writable and retry the failed removal.

    Propagate the original error if recovery fails.
    """
    # Check if the exception is an OSError and related to permissions
    # The specific error codes for read-only might vary, but AccessDenied (EACCES) is common.
    # We primarily check if we can make it writable.
    if isinstance(exc_info[1], OSError) and not os.access(path, os.W_OK):
        logger.debug(
            "Read-only error on path '%s'. Attempting to make it writable and retry.",
            path,
        )
        try:
            os.chmod(path, stat.S_IWUSR | stat.S_IWRITE)
            func(path)  # Retry the original function (e.g., os.remove or os.rmdir)
        except Exception as e_retry:
            logger.warning(
                "Failed to make '%s' writable and retry operation '%s': %s. Original error: %s",
                path,
                func.__name__,
                e_retry,
                exc_info[1],
            )
            # Re-raise the original exception if retry fails
            raise exc_info[1] from e_retry
    else:
        # If it's not an OSError we can handle or not a writable issue, re-raise the original exception.
        # For example, if the path is a directory that's not empty and func is os.rmdir.
        logger.debug(
            "Unhandled error during rmtree: %s on path %s. Re-raising.",
            exc_info[1],
            path,
        )
        raise exc_info[1]


async def delete_path_robustly(path_to_delete: str, item_description: str) -> bool:
    """Remove a path, retrying read-only entries where possible.

    Return ``True`` on deletion or absence, and ``False`` on removal failure.
    """
    if not isinstance(path_to_delete, str) or not path_to_delete:
        raise MissingArgumentError("path_to_delete cannot be empty.")
    if not isinstance(item_description, str) or not item_description:
        raise MissingArgumentError("item_description cannot be empty.")

    if not await aiofiles.ospath.exists(path_to_delete):
        logger.debug(
            "%s at '%s' not found, skipping.",
            item_description.capitalize(),
            path_to_delete,
        )
        return True

    if await aiofiles.ospath.isfile(path_to_delete):
        logger.debug(
            "Preparing to delete %s file: %s", item_description, path_to_delete
        )
        try:
            if not os.access(path_to_delete, os.W_OK):
                os.chmod(path_to_delete, stat.S_IWRITE | stat.S_IWUSR)
            await run_in_thread(os.remove, path_to_delete)
            logger.debug(
                "Successfully deleted %s file: %s", item_description, path_to_delete
            )
            return True
        except Exception as e:
            log_operation_error(
                logger,
                "Failed to delete %s file at '%s': %s",
                item_description,
                path_to_delete,
                e,
                error=e,
            )
            return False

    if await aiofiles.ospath.isdir(path_to_delete):
        logger.debug(
            "Preparing to delete %s directory: %s", item_description, path_to_delete
        )

        def _rmtree():
            shutil.rmtree(path_to_delete, onerror=_handle_remove_readonly_onerror)

        try:
            await run_in_thread(_rmtree)
            logger.debug(
                "Successfully deleted %s directory: %s",
                item_description,
                path_to_delete,
            )
            return True
        except Exception as e:
            log_operation_error(
                logger,
                "Failed to delete %s directory at '%s': %s",
                item_description,
                path_to_delete,
                e,
                error=e,
            )
            return False

    logger.warning(
        "Path '%s' is neither a regular file nor a directory. Deletion skipped.",
        path_to_delete,
    )
    return False


# --- RESOURCE MONITOR ---
class ProcessResourceMonitor:
    """Collect process CPU, memory and uptime observations."""

    _instance: Optional["ProcessResourceMonitor"] = None
    _lock = threading.Lock()

    def __new__(cls, *args: Any, **kwargs: Any) -> "ProcessResourceMonitor":
        """Ensure that only one instance of ProcessResourceMonitor is created (Singleton
        pattern).
        """
        if cls._instance is None:
            with cls._lock:
                # Double-check locking
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize the resource monitor's state.

        This constructor is called only once for the singleton instance. It sets up
        the ``_processes`` dictionary to cache psutil.Process objects and an
        ``_initialized`` flag.
        """
        if not hasattr(self, "_initialized"):  # Ensure this runs only once
            with self._lock:
                if not hasattr(self, "_initialized"):
                    self._processes: Dict[int, "psutil.Process"] = {}
                    self._initialized: bool = True

    def _cleanup_stale_processes(self) -> None:
        """Remove cached process objects that are no longer running."""
        dead_pids = []
        for pid, proc in self._processes.items():
            try:
                if not proc.is_running():
                    dead_pids.append(pid)
            except psutil.NoSuchProcess:
                dead_pids.append(pid)
        for pid in dead_pids:
            del self._processes[pid]

    def get_stats(self, process: "psutil.Process") -> Optional[Dict[str, Any]]:
        """Return PID, CPU percentage, memory in MiB and formatted uptime.

        Return ``None`` for inaccessible processes or an unavailable psutil
        dependency.
        """
        if not PSUTIL_AVAILABLE:
            logger.warning(
                "psutil is not available. Cannot get process stats for PID %s.",
                getattr(process, "pid", "N/A"),  # Safely get PID for log if possible
            )
            return None

        # Ensure psutil is available before using psutil.Process in isinstance
        if PSUTIL_AVAILABLE and not hasattr(process, "pid"):
            raise TypeError(
                f"Input must be a valid psutil.Process object, got {type(process).__name__}."
            )

        pid = process.pid

        # Periodically clean up stale processes
        self._cleanup_stale_processes()

        try:
            # Cache the process object so psutil can calculate the CPU delta internally
            if pid not in self._processes:
                self._processes[pid] = process
                process.cpu_percent(interval=None)  # Set the baseline

            cached_process = self._processes[pid]

            with cached_process.oneshot():  # Efficiently get multiple process infos
                cpu_percent = cached_process.cpu_percent(interval=None)

                memory_info = (
                    cached_process.memory_info()
                )  # specific type: psutil._common.smeninfo
                memory_mb = memory_info.rss / (1024 * 1024)  # RSS in MB

                create_time = cached_process.create_time()  # timestamp
                current_timestamp = time.time()
                uptime_seconds = current_timestamp - create_time
                uptime_str = str(timedelta(seconds=int(uptime_seconds)))

                return {
                    "pid": pid,
                    "cpu_percent": round(max(0.0, cpu_percent), 1),
                    "memory_mb": round(memory_mb, 1),
                    "uptime": uptime_str,
                }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            # If process disappears or access is denied, remove it from cache
            if pid in self._processes:
                del self._processes[pid]
            logger.debug(
                "Could not get stats for PID %s: Process gone or access denied.", pid
            )
            return None
        except Exception as e:
            # Catch any other psutil errors or unexpected issues
            raise SystemError(f"Failed to get stats for PID {pid}: {e}") from e
