# bedrock_server_manager/core/system/process.py
"""Cross-platform subprocess, identity verification and PID-file helpers."""

import asyncio
import logging
import os
import platform
import subprocess
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
    ServerStopError,
    SystemError,
)
from ...logging import log_operation_error

logger = logging.getLogger(__name__)


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
    """Return an absolute PID-file path below the configuration directory."""
    if (
        not isinstance(config_dir, str)
        or not config_dir
        or not await aiofiles.ospath.isdir(config_dir)
    ):
        raise AppFileNotFoundError(str(config_dir), "Configuration directory")
    if not pid_filename:
        raise MissingArgumentError("PID filename cannot be empty.")
    return os.path.join(config_dir, pid_filename)


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

    server_config_path = os.path.join(config_dir, server_name)
    if not await aiofiles.ospath.isdir(server_config_path):
        raise AppFileNotFoundError(
            server_config_path, f"Configuration directory for server '{server_name}'"
        )

    pid_filename = f"bedrock_{server_name}.pid"
    return os.path.join(server_config_path, pid_filename)


async def get_bedrock_launcher_pid_file_path(server_name: str, config_dir: str) -> str:
    """Return the detached launcher PID-file path."""
    if not isinstance(server_name, str) or not server_name:
        raise MissingArgumentError("Server name cannot be empty and must be a string.")
    if not isinstance(config_dir, str) or not config_dir:
        raise MissingArgumentError(
            "Configuration directory cannot be empty and must be a string."
        )

    if not await aiofiles.ospath.isdir(config_dir):
        try:
            # aiofiles.os doesn't have makedirs, so we use to_thread
            await run_in_thread(os.makedirs, config_dir, exist_ok=True)
            logger.debug(
                "Created configuration directory for launcher PID: %s", config_dir
            )
        except OSError as e:
            raise AppFileNotFoundError(
                config_dir,
                f"Launcher PID: Base config directory '{config_dir}' could not be created: {e}",
            ) from e

    pid_filename = f"bedrock_{server_name}_launcher.pid"
    return os.path.join(config_dir, pid_filename)


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
            os.makedirs(directory, exist_ok=True)
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


async def launch_detached_process(
    command: List[str], launcher_pid_file_path: str
) -> int:
    """Launch a guarded detached child and record its PID.

    Redirect standard streams to the null device; the child outlives the caller loop.
    """
    if not command or not command[0]:
        raise MissingArgumentError("Command list and executable cannot be empty.")
    if not isinstance(launcher_pid_file_path, str) or not launcher_pid_file_path:
        raise MissingArgumentError("Launcher PID file path cannot be empty.")

    logged_command = list(command)
    for index, argument in enumerate(logged_command[:-1]):
        if argument == "--db-url":
            logged_command[index + 1] = "<redacted>"
    logger.debug("Executing guarded detached command: %s", " ".join(logged_command))

    guarded_proc = GuardedProcess(command)

    creation_flags = 0
    start_new_session = False
    if platform.system() == "Windows":
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    else:
        start_new_session = True

    try:
        # A detached child must outlive the event loop used to launch it.
        # asyncio subprocess transports may kill their child when closed.
        process = await run_in_thread(
            guarded_proc.popen,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creation_flags,
            start_new_session=start_new_session,
            close_fds=True,
        )
    except FileNotFoundError:
        raise AppFileNotFoundError(command[0], "Command executable") from None
    except OSError as e:
        raise SystemError(f"OS error starting detached process: {e}") from e

    pid = process.pid
    logger.debug("Successfully started guarded process with PID: %s", pid)
    await write_pid_to_file(launcher_pid_file_path, pid)
    return pid


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
                    os.path.abspath(expected_executable_path)
                )
                proc_exe_norm = os.path.normcase(os.path.abspath(proc_exe))
                if proc_exe_norm != expected_exe_norm:
                    mismatches.append(
                        f"Executable path mismatch (Expected: '{expected_exe_norm}', Got: '{proc_exe_norm}')"
                    )

            # Verify Current Working Directory
            if expected_cwd:
                expected_cwd_norm = os.path.normcase(os.path.abspath(expected_cwd))
                proc_cwd_norm = os.path.normcase(os.path.abspath(proc_cwd))
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


async def get_verified_bedrock_process(
    server_name: str, server_dir: str, config_dir: str
) -> Optional["psutil.Process"]:
    """Asynchronously finds, verifies, and returns the Bedrock server process using its PID file.

    This function utilizes the async variants of the core system checks to verify
    if a Bedrock server process is currently running and matches expectations.
    """
    if not PSUTIL_AVAILABLE:
        logger.error("'psutil' is required for this function. Returning None.")
        return None

    if not isinstance(server_name, str) or not server_name:
        logger.debug("Cannot verify process without a server name.")
        return None
    if (
        not isinstance(server_dir, str)
        or not server_dir
        or not await aiofiles.ospath.isdir(server_dir)
    ):
        logger.debug(
            "get_verified_bedrock_process: server_dir '%s' is invalid or not a directory.",
            server_dir,
        )
        return None
    if (
        not isinstance(config_dir, str)
        or not config_dir
        or not await aiofiles.ospath.isdir(config_dir)
    ):
        logger.debug(
            "get_verified_bedrock_process: config_dir '%s' is invalid or not a directory.",
            config_dir,
        )
        return None

    try:
        pid_file_path = await get_bedrock_server_pid_file_path(server_name, config_dir)
        pid = await read_pid_from_file(pid_file_path)

        if pid is None:
            logger.debug("No valid PID found in file for server '%s'.", server_name)
            return None

        if not await is_process_running(pid):
            logger.debug(
                "Stale PID %s found for '%s'. Process not running.", pid, server_name
            )
            await remove_pid_file_if_exists(pid_file_path)
            return None

        exe_name = (
            "bedrock_server.exe" if platform.system() == "Windows" else "bedrock_server"
        )
        expected_exe_abs = os.path.abspath(os.path.join(server_dir, exe_name))
        expected_cwd_abs = os.path.abspath(server_dir)

        await verify_process_identity(
            pid,
            expected_executable_path=expected_exe_abs,
            expected_cwd=expected_cwd_abs,
        )

        return psutil.Process(pid)

    except (
        AppFileNotFoundError,  # From get_bedrock_server_pid_file_path or verify if paths are bad
        FileOperationError,  # From read_pid_from_file
        ServerProcessError,  # From await verify_process_identity
        PermissionsError,  # From await verify_process_identity
        MissingArgumentError,  # From called functions if somehow inputs are bad despite checks
    ) as e:
        # These are expected "not running" or "mismatch" scenarios.
        logger.debug("Verification failed for server '%s': %s", server_name, e)
        # Attempt to clean up PID file if verification failed for a running PID
        if (
            "pid" in locals()
            and pid is not None
            and await aiofiles.ospath.exists(pid_file_path)
        ):
            if isinstance(e, ServerProcessError):  # Mismatch
                logger.debug(
                    "Cleaning up PID file '%s' due to verification mismatch for PID %s.",
                    pid_file_path,
                    pid,
                )
                await remove_pid_file_if_exists(pid_file_path)
        return None
    except (
        SystemError,
        Exception,
    ) as e:  # SystemError from psutil functions, or any other unexpected
        # These are more serious, unexpected errors.
        log_operation_error(
            logger,
            "Unexpected error getting verified process for '%s': %s",
            server_name,
            e,
            error=e,
        )
        return None


async def terminate_process_by_pid(  # noqa: C901
    pid: int, terminate_timeout: int = 5, kill_timeout: int = 2
):
    """Terminate a process, then kill it if the first deadline expires.

    Timeouts are seconds. Windows termination is forceful; POSIX termination uses
    SIGTERM. Propagate failures to confirm process exit.
    """
    if not PSUTIL_AVAILABLE:
        raise SystemError("psutil package is required to terminate processes.")
    if not isinstance(pid, int):
        raise MissingArgumentError("PID must be an integer.")
    if not (isinstance(terminate_timeout, int) and terminate_timeout >= 0):
        raise ServerStopError("terminate_timeout must be a non-negative integer.")
    if not (isinstance(kill_timeout, int) and kill_timeout >= 0):
        raise ServerStopError("kill_timeout must be a non-negative integer.")

    try:

        def _terminate() -> None:
            process = psutil.Process(pid)
            # 1. Attempt graceful termination first.
            logger.debug("Attempting graceful termination (SIGTERM) for PID %s...", pid)
            process.terminate()
            try:
                process.wait(timeout=terminate_timeout)
                logger.debug("Process %s terminated gracefully.", pid)
            except psutil.TimeoutExpired:
                # 2. If graceful termination fails, resort to forceful killing.
                logger.warning(
                    "Process %s did not terminate gracefully within %ss. Attempting kill (SIGKILL)...",
                    pid,
                    terminate_timeout,
                )
                process.kill()
                process.wait(timeout=kill_timeout)
                logger.info("Process %s forcefully killed.", pid)

        await run_in_thread(_terminate)
    except psutil.NoSuchProcess:
        # This is not an error; the process is already gone.
        logger.debug(
            "Process with PID %s disappeared or was already stopped during termination attempt.",
            pid,
        )
    except psutil.AccessDenied:
        raise PermissionsError(
            f"Permission denied trying to terminate process with PID {pid}."
        )
    except Exception as e:
        raise ServerStopError(
            f"Unexpected error terminating process PID {pid}: {e}"
        ) from e


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
