# bedrock_server_manager/core/system/process.py
"""Cross-platform subprocess, identity verification and PID-file helpers."""

import asyncio
import logging
import os
import platform
import subprocess
import time
from typing import Any, Dict, List, Optional, Sequence, Union

import aiofiles
import aiofiles.os
import aiofiles.ospath

from ...utils.threads import run_in_thread

try:
    import psutil

    PSUTIL_AVAILABLE = True
    """bool: ``True`` if the `psutil` library was successfully imported, ``False`` otherwise.
    Many functions in this module depend on `psutil` and will raise a
    :class:`SystemError` or return degraded functionality if it's not available.
    """
except ImportError:
    PSUTIL_AVAILABLE = False
    # Ensure PSUTIL_AVAILABLE is defined even if import fails, for type checkers
    # and to prevent NameError if accessed before a check.
    # The docstring above will be associated with the True assignment by Sphinx.

from ...config import GUARD_VARIABLE
from ...error import (
    AppFileNotFoundError,
    FileOperationError,
    MissingArgumentError,
    PermissionsError,
    ServerProcessError,
    SystemError,
)
from ...logging import log_operation_error

logger = logging.getLogger(__name__)

UNTRACKED_SCAN_INTERVAL_SECONDS: float = 5.0


class ProcessRecoveryState:
    """Coordinate probes within one server owner; never share application state globally."""

    def __init__(self) -> None:
        self.locks: dict[tuple[str, str, str], asyncio.Lock] = {}
        self.last_negative_scan: dict[tuple[str, str, str], float] = {}
        self.recovered_pids: dict[tuple[str, str, str], int] = {}

    @staticmethod
    def key(server_name: str, server_dir: str, config_dir: str) -> tuple[str, str, str]:
        return (
            server_name,
            os.path.normcase(os.path.realpath(server_dir)),
            os.path.normcase(os.path.realpath(config_dir)),
        )

    def clear(self) -> None:
        self.last_negative_scan.clear()
        self.recovered_pids.clear()


class GuardedProcess:
    """Run subprocesses with the application recursion-guard environment set."""

    def __init__(self, command: Sequence[Union[str, os.PathLike]]):
        """Initialize the GuardedProcess with the command to be run.

        :param command: A list representing the
                        command and its arguments (e.g., ``['python', 'app.py', '--start-server']``).
        """
        self.command = command
        self.guard_env = self._create_guarded_environment()

    def _create_guarded_environment(self) -> Dict[str, str]:
        """Create a copy of the current environment with the guard variable set.

        The guard variable is defined by
        :const:`~bedrock_server_manager.config.const.GUARD_VARIABLE`.

        :returns: A new dictionary representing the modified environment.
        """
        child_env = os.environ.copy()
        child_env[GUARD_VARIABLE] = "1"
        return child_env

    def run(self, **kwargs: Any) -> subprocess.CompletedProcess:
        """Run the command with the guarded environment, replacing any supplied ``env``."""
        kwargs["env"] = self.guard_env
        return subprocess.run(self.command, **kwargs)

    def popen(self, **kwargs: Any) -> subprocess.Popen:
        """Spawn the command with the guarded environment, replacing any supplied
        ``env``.
        """
        kwargs["env"] = self.guard_env
        return subprocess.Popen(self.command, **kwargs)

    async def create_subprocess_exec(self, **kwargs: Any) -> asyncio.subprocess.Process:
        """Wrap ``asyncio.create_subprocess_exec``, injecting the guarded environment.

        :param kwargs: Keyword arguments to pass directly.
                           If ``env`` is provided in ``kwargs``, it will be overwritten.
        :type kwargs: Any

        :returns: The asynchronous process object.
        """
        kwargs["env"] = self.guard_env
        return await asyncio.create_subprocess_exec(*self.command, **kwargs)

    async def create_subprocess_shell(
        self, **kwargs: Any
    ) -> asyncio.subprocess.Process:
        """Wrap ``asyncio.create_subprocess_shell``, injecting the guarded environment.

        :param kwargs: Keyword arguments to pass directly.
                           If ``env`` is provided in ``kwargs``, it will be overwritten.
        :type kwargs: Any

        :returns: The asynchronous process object.
        """
        kwargs["env"] = self.guard_env
        import shlex

        cmd_str = shlex.join(str(arg) for arg in self.command)
        return await asyncio.create_subprocess_shell(cmd_str, **kwargs)


async def get_pid_file_path(config_dir: str, pid_filename: str) -> str:
    """Return an absolute PID-file path below the configuration runtime directory."""
    if (
        not isinstance(config_dir, str)
        or not config_dir
        or not await aiofiles.ospath.isdir(config_dir)
    ):
        raise AppFileNotFoundError(str(config_dir), "Configuration directory")
    if not pid_filename:
        raise MissingArgumentError("PID filename cannot be empty.")
    return os.path.join(config_dir, "runtime", pid_filename)


async def get_bedrock_server_pid_file_path(server_name: str, config_dir: str) -> str:
    """Return the server process PID-file path."""
    if not isinstance(server_name, str) or not server_name:
        raise MissingArgumentError("Server name cannot be empty and must be a string.")
    if not isinstance(config_dir, str) or not config_dir:
        raise MissingArgumentError(
            "Configuration directory cannot be empty and must be a string."
        )

    if not await aiofiles.ospath.isdir(config_dir):
        raise AppFileNotFoundError(config_dir, "Base configuration directory")
    if not config_dir:
        raise MissingArgumentError("Configuration directory cannot be empty.")

    server_config_path = os.path.join(config_dir, "runtime", "servers", server_name)
    if not await aiofiles.ospath.isdir(server_config_path):
        raise AppFileNotFoundError(
            server_config_path, f"Configuration directory for server '{server_name}'"
        )

    pid_filename = f"bedrock_{server_name}.pid"
    return os.path.join(server_config_path, pid_filename)


async def read_pid_from_file(pid_file_path: str) -> Optional[int]:
    """Read an integer PID, or return ``None`` for absent, empty or unreadable files."""
    if not isinstance(pid_file_path, str) or not pid_file_path:
        raise MissingArgumentError("PID file path cannot be empty.")

    if not await aiofiles.ospath.exists(pid_file_path):
        logger.debug("PID file not found: %s", pid_file_path)
        return None

    try:
        async with aiofiles.open(pid_file_path, "r", encoding="utf-8") as f:
            content = await f.read()
            pid_str = content.strip()
            if not pid_str:
                logger.warning("PID file is empty: %s", pid_file_path)
                return None
            return int(pid_str)
    except ValueError:
        logger.warning(
            "Invalid content in PID file '%s'. Expected an integer.", pid_file_path
        )
        return None
    except OSError as e:
        log_operation_error(
            logger, "Error reading PID file '%s': %s", pid_file_path, e, error=e
        )
        return None


async def write_pid_to_file(pid_file_path: str, pid: int):
    """Write an integer PID to its file; propagate invalid arguments and write failures."""
    if not isinstance(pid_file_path, str) or not pid_file_path:
        raise MissingArgumentError("PID file path cannot be empty.")
    if not isinstance(pid, int):
        raise MissingArgumentError("PID must be an integer.")

    directory = os.path.dirname(pid_file_path)
    if directory and not await aiofiles.ospath.exists(directory):
        try:
            await aiofiles.os.makedirs(directory, exist_ok=True)
            logger.debug("Created directory for PID file: %s", directory)
        except OSError as e:
            raise FileOperationError(
                f"Failed to create directory '{directory}' for PID file: {e}"
            ) from e

    try:
        async with aiofiles.open(pid_file_path, "w", encoding="utf-8") as f:
            await f.write(str(pid))
        logger.debug("Wrote PID %s to '%s'", pid, pid_file_path)
    except OSError as e:
        raise FileOperationError(
            f"Failed to write PID {pid} to '{pid_file_path}': {e}"
        ) from e


async def is_process_running(pid: int) -> bool:
    """Return whether the PID exists according to psutil."""
    if not PSUTIL_AVAILABLE:
        raise SystemError(
            "psutil package is required to check if a process is running."
        )
    if not isinstance(pid, int):
        raise MissingArgumentError("PID must be an integer.")
    return await run_in_thread(psutil.pid_exists, pid)


async def verify_process_identity(  # noqa: C901
    pid: int,
    expected_executable_path: Optional[str] = None,
    expected_cwd: Optional[str] = None,
    expected_command_args: Optional[Union[str, List[str]]] = None,
):
    """Verify a PID against supplied executable, directory and argument criteria.

    Raise ``ServerProcessError`` for missing or mismatched processes; path comparisons
    are normalized and case-insensitive.
    """
    if not PSUTIL_AVAILABLE:
        raise SystemError("psutil package is required for process verification.")
    if not isinstance(pid, int):
        raise MissingArgumentError("PID must be an integer.")
    if not any([expected_executable_path, expected_cwd, expected_command_args]):
        raise MissingArgumentError(
            "At least one verification criteria must be provided."
        )

    try:

        def _verify():
            proc = psutil.Process(pid)
            # Use oneshot() for performance, as it caches process info for subsequent calls.
            with proc.oneshot():
                proc_name = proc.name()
                proc_exe = proc.exe()
                proc_cwd = proc.cwd()
                proc_cmdline = proc.cmdline()

            mismatches = []
            # Verify Executable Path
            if expected_executable_path:
                expected_exe_norm = os.path.normcase(
                    os.path.realpath(expected_executable_path)
                )
                proc_exe_norm = os.path.normcase(os.path.realpath(proc_exe))
                if proc_exe_norm != expected_exe_norm:
                    mismatches.append(
                        f"Executable path mismatch (Expected: '{expected_exe_norm}', Got: '{proc_exe_norm}')"
                    )

            # Verify Current Working Directory
            if expected_cwd:
                expected_cwd_norm = os.path.normcase(os.path.realpath(expected_cwd))
                proc_cwd_norm = os.path.normcase(os.path.realpath(proc_cwd))
                if proc_cwd_norm != expected_cwd_norm:
                    mismatches.append(
                        f"CWD mismatch (Expected: '{expected_cwd_norm}', Got: '{proc_cwd_norm}')"
                    )

            # Verify Command Arguments
            if expected_command_args:
                args_to_check = (
                    [expected_command_args]
                    if isinstance(expected_command_args, str)
                    else expected_command_args
                )
                if not all(arg in proc_cmdline for arg in args_to_check):
                    mismatches.append(
                        f"Argument mismatch (Expected '{args_to_check}' in command line)"
                    )

            if mismatches:
                details = ", ".join(mismatches)
                raise ServerProcessError(
                    f"PID {pid} (Name: {proc_name}) failed verification: {details}. Cmd: '{' '.join(proc_cmdline)}'"
                )

            return proc_name

        proc_name = await run_in_thread(_verify)
    except psutil.NoSuchProcess:
        raise ServerProcessError(
            f"Process with PID {pid} does not exist for verification."
        )
    except psutil.AccessDenied:
        raise PermissionsError(f"Access denied when trying to get info for PID {pid}.")
    except psutil.Error as e_psutil:
        raise SystemError(f"Error getting process info for PID {pid}: {e_psutil}.")
    except ServerProcessError:
        raise

    logger.debug(
        "Process %s (Name: %s) verified successfully against signature.", pid, proc_name
    )


def find_untracked_server_process(server_dir: str) -> Optional[int]:
    """Find exactly one process matching both executable and working directory.

    Reject ambiguity rather than adopting an arbitrary process. Normalize paths
    identically to verify_process_identity; inaccessible candidates are skipped.
    """
    target_dir = os.path.normcase(os.path.realpath(server_dir))
    exe_name = (
        "bedrock_server.exe" if platform.system() == "Windows" else "bedrock_server"
    )
    expected_exe = os.path.join(target_dir, exe_name)
    matches: list[int] = []
    if not PSUTIL_AVAILABLE:
        raise SystemError("psutil is required for process discovery.")
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            if str(proc.info.get("name", "")).lower() != exe_name.lower():
                continue
            with proc.oneshot():
                if (
                    os.path.normcase(os.path.realpath(proc.cwd())) == target_dir
                    and os.path.normcase(os.path.realpath(proc.exe())) == expected_exe
                    and proc.status() != psutil.STATUS_ZOMBIE
                ):
                    matches.append(int(proc.pid))
        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
            continue
    if len(matches) > 1:
        raise ServerProcessError(
            f"Multiple Bedrock processes match '{server_dir}': {matches}. Recovery requires attention."
        )
    return matches[0] if matches else None


async def get_verified_bedrock_process(
    server_name: str,
    server_dir: str,
    config_dir: str,
    *,
    scan_interval_sec: Optional[float] = None,
    recover_untracked: bool = True,
    recovery_state: ProcessRecoveryState | None = None,
    force_scan: bool = False,
) -> Optional["psutil.Process"]:
    """Verify or discover a process, serializing concurrent probes for this owner.

    Only completed negative scans are cached. Lifecycle callers bypass that cache.
    Unexpected verification/discovery failures propagate so they cannot authorize
    starting a duplicate server. Direct callers may supply their own scoped state.
    """
    if not PSUTIL_AVAILABLE:
        raise SystemError("psutil is required for process verification.")
    if not server_name:
        raise MissingArgumentError("Server name is required.")
    if not server_dir or not await aiofiles.ospath.isdir(server_dir):
        return None
    if not config_dir or not await aiofiles.ospath.isdir(config_dir):
        return None
    state = recovery_state if recovery_state is not None else ProcessRecoveryState()
    key = state.key(server_name, server_dir, config_dir)
    async with state.locks.setdefault(key, asyncio.Lock()):
        try:
            pid_file_path = await get_bedrock_server_pid_file_path(
                server_name, config_dir
            )
        except AppFileNotFoundError:
            # An installation without a runtime directory can still have an orphan.
            pid_file_path = os.path.join(
                config_dir,
                "runtime",
                "servers",
                server_name,
                f"bedrock_{server_name}.pid",
            )
        pid = await read_pid_from_file(pid_file_path)
        exe_name = (
            "bedrock_server.exe" if platform.system() == "Windows" else "bedrock_server"
        )
        expected_exe = os.path.join(server_dir, exe_name)
        if pid is not None:
            try:
                await verify_process_identity(
                    pid, expected_executable_path=expected_exe, expected_cwd=server_dir
                )
                process = psutil.Process(pid)
                if await run_in_thread(process.status) != psutil.STATUS_ZOMBIE:
                    state.last_negative_scan.pop(key, None)
                    return process
            except ServerProcessError:
                pass
            if not await remove_pid_file_if_exists(pid_file_path):
                raise FileOperationError(
                    f"Cannot remove stale PID file '{pid_file_path}'."
                )
            state.recovered_pids.pop(key, None)
            state.last_negative_scan.pop(key, None)
        if not recover_untracked:
            return None
        interval = (
            scan_interval_sec
            if scan_interval_sec is not None
            else UNTRACKED_SCAN_INTERVAL_SECONDS
        )
        last_scan = state.last_negative_scan.get(key)
        if (
            not force_scan
            and last_scan is not None
            and time.monotonic() - last_scan < interval
        ):
            return None
        pid = await run_in_thread(find_untracked_server_process, server_dir)
        if pid is None:
            state.last_negative_scan[key] = time.monotonic()
            state.recovered_pids.pop(key, None)
            return None
        # Do not publish a candidate until final verification and PID persistence succeed.
        await verify_process_identity(
            pid, expected_executable_path=expected_exe, expected_cwd=server_dir
        )
        process = psutil.Process(pid)
        if await run_in_thread(process.status) == psutil.STATUS_ZOMBIE:
            return None
        await write_pid_to_file(pid_file_path, pid)
        state.recovered_pids[key] = pid
        state.last_negative_scan.pop(key, None)
        logger.warning(
            "Recovered verified Bedrock process %s for '%s'; console commands remain unavailable.",
            pid,
            server_name,
        )
        return process


async def remove_pid_file_if_exists(pid_file_path: str) -> bool:
    """Remove a PID file if present; return ``False`` if removal fails."""
    if not isinstance(pid_file_path, str) or not pid_file_path:
        raise MissingArgumentError("PID file path cannot be empty.")

    if await aiofiles.ospath.exists(pid_file_path):
        try:
            await run_in_thread(os.remove, pid_file_path)
            logger.debug("Removed PID file '%s'.", pid_file_path)
            return True
        except OSError as e:
            logger.warning("Could not remove PID file '%s': %s", pid_file_path, e)
            return False
    return True
