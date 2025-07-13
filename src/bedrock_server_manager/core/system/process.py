# bedrock_server_manager/core/system/process.py
"""Provides generic, cross-platform process management utilities.

This module abstracts common tasks related to system process interaction,
aiming to provide a consistent interface regardless of the underlying OS
(though some behaviors might be platform-specific, as noted in function
docstrings). It is crucial for managing Bedrock server processes, launcher
processes, and potentially other child processes.

The module heavily relies on the ``psutil`` library for many of its
capabilities. Its availability is checked by the :const:`PSUTIL_AVAILABLE` flag,
and functions requiring ``psutil`` will typically raise a :class:`SystemError`
if it's not installed.

Key Functionality Groups:

    - **PID File Management**:
        - :func:`get_pid_file_path`,
        - :func:`get_bedrock_server_pid_file_path`,
        - :func:`get_bedrock_launcher_pid_file_path`,
        - :func:`read_pid_from_file`,
        - :func:`write_pid_to_file`,
        - :func:`remove_pid_file_if_exists`.
    - **Process Status & Verification**:
        - :func:`is_process_running`,
        - :func:`verify_process_identity`,
        - :func:`get_verified_bedrock_process`.
    - **Process Creation & Termination**:
        - :func:`launch_detached_process` (using :class:`GuardedProcess`),
        - :func:`terminate_process_by_pid`.
    - **Guarded Subprocessing**:
        - :class:`GuardedProcess`: A wrapper around ``subprocess`` to inject a
          recursion guard environment variable, preventing re-initialization loops
          when the application calls itself.

Constants:
    - :const:`PSUTIL_AVAILABLE`: Boolean indicating if ``psutil`` was imported.
"""
import os
import logging
import subprocess
import platform
import sys
from typing import Optional, List, Dict, Union, Any


# psutil is an optional dependency, but required for most functions here.
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
    FileOperationError,
    SystemError,
    ServerProcessError,
    AppFileNotFoundError,
    MissingArgumentError,
    PermissionsError,
    ServerStopError,
)

logger = logging.getLogger(__name__)


class GuardedProcess:
    """Wraps ``subprocess`` calls to inject a recursion guard environment variable.

    When the application needs to launch a new instance of itself as a subprocess
    (e.g., to start a server in a detached background process via
    :func:`launch_detached_process`), this class is used to manage the subprocess
    creation.

    Its primary purpose is to set a specific environment variable, defined by
    :const:`~bedrock_server_manager.config.const.GUARD_VARIABLE` (e.g.,
    ``BSM_GUARDED_EXECUTION="1"``), in the environment of the child process.
    The application's main entry point or initialization logic can then check
    for the presence of this variable. If detected, it can skip certain
    initialization steps (like reloading plugins, re-parsing arguments for the
    main CLI) that are unnecessary or problematic for a guarded, secondary instance.
    This helps prevent issues like duplicate plugin loading or unintended
    recursive behavior.

    The class provides :meth:`run` and :meth:`popen` methods that mirror the
    standard ``subprocess.run`` and ``subprocess.Popen`` functions but ensure
    the guarded environment is passed to the child process.

    Attributes:
        command (List[Union[str, os.PathLike]]): The command and its arguments.
        guard_env (Dict[str, str]): A copy of the current environment with the
            guard variable added.
    """

    def __init__(self, command: List[Union[str, os.PathLike]]):
        """Initializes the GuardedProcess with the command to be run.

        Args:
            command (List[Union[str, os.PathLike]]): A list representing the
                command and its arguments (e.g., ``['python', 'app.py', '--start-server']``).
        """
        self.command = command
        self.guard_env = self._create_guarded_environment()

    def _create_guarded_environment(self) -> Dict[str, str]:
        """Creates a copy of the current environment with the guard variable set.

        The guard variable is defined by
        :const:`~bedrock_server_manager.config.const.GUARD_VARIABLE`.

        Returns:
            Dict[str, str]: A new dictionary representing the modified environment.
        """
        child_env = os.environ.copy()
        child_env[GUARD_VARIABLE] = "1"
        return child_env

    def run(self, **kwargs: Any) -> subprocess.CompletedProcess:
        """Wraps ``subprocess.run``, injecting the guarded environment.

        This method calls ``subprocess.run`` with the stored ``self.command``
        and passes along any additional ``**kwargs``. The crucial difference is
        that it automatically sets the ``env`` keyword argument for
        ``subprocess.run`` to ``self.guard_env``.

        Args:
            **kwargs (Any): Keyword arguments to pass directly to ``subprocess.run``.
                If ``env`` is provided in ``kwargs``, it will be overwritten.

        Returns:
            subprocess.CompletedProcess: The result of the ``subprocess.run`` call.
        """
        kwargs["env"] = self.guard_env
        return subprocess.run(self.command, **kwargs)

    def popen(self, **kwargs: Any) -> subprocess.Popen:
        """Wraps ``subprocess.Popen``, injecting the guarded environment.

        This method calls ``subprocess.Popen`` with the stored ``self.command``
        and passes along any additional ``**kwargs``. The crucial difference is
        that it automatically sets the ``env`` keyword argument for
        ``subprocess.Popen`` to ``self.guard_env``.

        Args:
            **kwargs (Any): Keyword arguments to pass directly to ``subprocess.Popen``.
                If ``env`` is provided in ``kwargs``, it will be overwritten.

        Returns:
            subprocess.Popen: The ``subprocess.Popen`` object for the new process.
        """
        kwargs["env"] = self.guard_env
        return subprocess.Popen(self.command, **kwargs)


def get_pid_file_path(config_dir: str, pid_filename: str) -> str:
    """Constructs the full, absolute path for a generic PID file.

    This utility function joins the provided configuration directory and PID
    filename to produce a standardized, absolute path for a PID file.

    Args:
        config_dir (str): The absolute path to the application's (or a specific
            component's) configuration directory where the PID file should reside.
        pid_filename (str): The base name of the PID file (e.g., "web_server.pid",
            "my_process.pid").

    Returns:
        str: The absolute path to where the PID file should be stored.

    Raises:
        AppFileNotFoundError: If `config_dir` is not provided, is not a string,
            or is not an existing directory.
        MissingArgumentError: If `pid_filename` is not provided or is an empty string.
    """
    if (
        not isinstance(config_dir, str)
        or not config_dir
        or not os.path.isdir(config_dir)
    ):
        raise AppFileNotFoundError(str(config_dir), "Configuration directory")
    if not pid_filename:
        raise MissingArgumentError("PID filename cannot be empty.")
    return os.path.join(config_dir, pid_filename)


def get_bedrock_server_pid_file_path(server_name: str, config_dir: str) -> str:
    """Constructs the standardized path to a Bedrock server's main process PID file.

    This function generates a path for a PID file specific to a Bedrock server
    instance. The PID file is typically located in a subdirectory named after the
    `server_name` within the main `config_dir`. The filename itself is
    ``bedrock_<server_name>.pid``.

    Example:
        If `server_name` is "MyServer" and `config_dir` is "/opt/bsm/.config",
        the returned path might be "/opt/bsm/.config/MyServer/bedrock_MyServer.pid".

    Args:
        server_name (str): The unique name of the server instance.
        config_dir (str): The main configuration directory for the application.
            This directory must exist.

    Returns:
        str: The absolute path to where the server's PID file should be located.

    Raises:
        MissingArgumentError: If `server_name` or `config_dir` are empty or not strings.
        AppFileNotFoundError: If the `config_dir` does not exist, or if the
            derived server-specific config subdirectory (e.g., `<config_dir>/<server_name>`)
            does not exist.
    """
    if not isinstance(server_name, str) or not server_name:
        raise MissingArgumentError("Server name cannot be empty and must be a string.")
    if not isinstance(config_dir, str) or not config_dir:
        raise MissingArgumentError(
            "Configuration directory cannot be empty and must be a string."
        )

    # Ensure base config_dir exists first, as server_config_path depends on it.
    if not os.path.isdir(config_dir):
        raise AppFileNotFoundError(config_dir, "Base configuration directory")
    if not config_dir:
        raise MissingArgumentError("Configuration directory cannot be empty.")

    server_config_path = os.path.join(config_dir, server_name)
    if not os.path.isdir(server_config_path):
        raise AppFileNotFoundError(
            server_config_path, f"Configuration directory for server '{server_name}'"
        )

    pid_filename = f"bedrock_{server_name}.pid"
    return os.path.join(server_config_path, pid_filename)


def get_bedrock_launcher_pid_file_path(server_name: str, config_dir: str) -> str:
    """Constructs the path for a Bedrock server's LAUNCHER process PID file.

    This PID file is intended for the "launcher" or "wrapper" process that
    manages the actual Bedrock server (e.g., a process started by this application
    to run the server in the background or foreground with IPC).
    The PID file is typically named ``bedrock_<server_name>_launcher.pid`` and is
    placed directly in the provided `config_dir` (unlike the server's own PID
    file which might be in a subdirectory).

    If `config_dir` does not exist, this function will attempt to create it.

    Args:
        server_name (str): The unique name of the server instance this launcher
            is associated with.
        config_dir (str): The main configuration directory for the application.
            If it doesn't exist, an attempt will be made to create it.

    Returns:
        str: The absolute path to where the launcher's PID file should be located.

    Raises:
        MissingArgumentError: If `server_name` or `config_dir` are empty or not strings.
        AppFileNotFoundError: If `config_dir` does not exist and cannot be created.
    """
    if not isinstance(server_name, str) or not server_name:
        raise MissingArgumentError("Server name cannot be empty and must be a string.")
    if not isinstance(config_dir, str) or not config_dir:
        raise MissingArgumentError(
            "Configuration directory cannot be empty and must be a string."
        )

    # For launcher PID, config_dir is the direct parent. Create if not exists.
    if not os.path.isdir(config_dir):
        try:
            os.makedirs(config_dir, exist_ok=True)
            logger.info(
                f"Created configuration directory for launcher PID: {config_dir}"
            )
        except OSError as e:
            raise AppFileNotFoundError(
                config_dir,
                f"Launcher PID: Base config directory '{config_dir}' could not be created: {e}",
            ) from e

    pid_filename = f"bedrock_{server_name}_launcher.pid"
    return os.path.join(config_dir, pid_filename)


def read_pid_from_file(pid_file_path: str) -> Optional[int]:
    """Reads and validates a Process ID (PID) from a specified file.

    If the PID file exists, this function attempts to read its content, strip
    any leading/trailing whitespace, and convert it to an integer.

    Args:
        pid_file_path (str): The absolute path to the PID file.

    Returns:
        Optional[int]: The PID as an integer if the file exists, is readable,
        and contains a valid integer. Returns ``None`` if the PID file does not
        exist at `pid_file_path`.

    Raises:
        MissingArgumentError: If `pid_file_path` is not provided or is empty.
        FileOperationError: If the file exists but cannot be read (e.g., due to
            permissions) or if its content is not a valid integer.
    """
    if not isinstance(pid_file_path, str) or not pid_file_path:
        raise MissingArgumentError("PID file path cannot be empty.")

    if not os.path.isfile(pid_file_path):
        logger.debug(f"PID file '{pid_file_path}' not found.")
        return None
    try:
        with open(pid_file_path, "r") as f:
            pid_str = f.read().strip()
        if not pid_str.isdigit():
            raise FileOperationError(
                f"Invalid content in PID file '{pid_file_path}': '{pid_str}'."
            )
        return int(pid_str)
    except (OSError, ValueError) as e:
        raise FileOperationError(
            f"Error reading or parsing PID file '{pid_file_path}': {e}"
        ) from e


def write_pid_to_file(pid_file_path: str, pid: int):
    """Writes a process ID (PID) to the specified file, creating directories if needed.

    This function writes the given `pid` (converted to a string) to the file
    at `pid_file_path`. If the parent directory (or directories) for
    `pid_file_path` do not exist, they will be created. Any existing content
    in the file will be overwritten.

    Args:
        pid_file_path (str): The absolute path to the PID file where the PID
            should be written.
        pid (int): The process ID to write to the file.

    Raises:
        MissingArgumentError: If `pid_file_path` is not provided or is empty,
            or if `pid` is not an integer.
        FileOperationError: If an ``OSError`` occurs while creating directories
            or writing to the file (e.g., permission issues).
    """
    if not isinstance(pid_file_path, str) or not pid_file_path:
        raise MissingArgumentError("PID file path cannot be empty.")
    if not isinstance(pid, int):
        raise MissingArgumentError("PID must be an integer.")

    try:
        # Ensure the directory for the PID file exists.
        pid_dir = os.path.dirname(pid_file_path)
        if pid_dir:  # Only create if dirname is not empty (e.g. not for root files)
            os.makedirs(pid_dir, exist_ok=True)

        with open(pid_file_path, "w") as f:
            f.write(str(pid))
        logger.info(f"Saved PID {pid} to '{pid_file_path}'.")
    except OSError as e:
        raise FileOperationError(
            f"Failed to write PID {pid} to file '{pid_file_path}': {e}"
        ) from e


def is_process_running(pid: int) -> bool:
    """Checks if a process with the given PID is currently running.

    This function relies on ``psutil.pid_exists()`` to determine if a process
    with the specified `pid` is active on the system.

    Args:
        pid (int): The process ID to check.

    Returns:
        bool: ``True`` if a process with the given `pid` exists and is running,
        ``False`` otherwise.

    Raises:
        SystemError: If the ``psutil`` library is not available (i.e.,
            :const:`PSUTIL_AVAILABLE` is ``False``).
        MissingArgumentError: If `pid` is not an integer.
    """
    if not PSUTIL_AVAILABLE:
        raise SystemError(
            "psutil package is required to check if a process is running."
        )
    if not isinstance(pid, int):
        raise MissingArgumentError("PID must be an integer.")
    return psutil.pid_exists(pid)


def launch_detached_process(command: List[str], launcher_pid_file_path: str) -> int:
    """Launches a command as a detached background process and records its PID.

    This function uses the :class:`GuardedProcess` wrapper to execute the given
    `command`. The `GuardedProcess` injects a recursion guard environment
    variable into the child process.

    Platform-specific ``subprocess.Popen`` flags are used to ensure the new
    process is fully detached from the parent and runs independently in the
    background:

        - On Windows: ``subprocess.CREATE_NO_WINDOW`` is used.
        - On POSIX systems (Linux, macOS): ``start_new_session=True`` is used.

    Standard input, output, and error streams of the new process are redirected
    to ``subprocess.DEVNULL``.

    The PID of the newly launched detached process is written to the file specified
    by `launcher_pid_file_path` using :func:`write_pid_to_file`.

    Args:
        command (List[str]): The command and its arguments as a list of strings
            (e.g., ``['python', 'my_script.py', '--daemon']``). The first element
            should be the executable.
        launcher_pid_file_path (str): The absolute path to the file where the PID
            of the newly launched launcher/detached process should be written.

    Returns:
        int: The Process ID (PID) of the newly launched detached process.

    Raises:
        MissingArgumentError: If `command` is empty, its first element (executable)
            is empty, or if `launcher_pid_file_path` is empty.
        AppFileNotFoundError: If the executable specified in `command[0]`
            is not found on the system.
        SystemError: For other OS-level errors that occur during process creation
            (e.g., permission issues, resource limits).
        FileOperationError: If writing the PID to `launcher_pid_file_path` fails.
    """
    if not command or not command[0]:
        raise MissingArgumentError("Command list and executable cannot be empty.")
    if not isinstance(launcher_pid_file_path, str) or not launcher_pid_file_path:
        raise MissingArgumentError("Launcher PID file path cannot be empty.")

    logger.info(f"Executing guarded detached command: {' '.join(command)}")

    guarded_proc = GuardedProcess(command)

    # Set platform-specific flags for detaching the process.
    creation_flags = 0
    start_new_session = False
    if platform.system() == "Windows":
        # Prevents the new process from opening a console window.
        creation_flags = subprocess.CREATE_NO_WINDOW
    else:  # Linux, Darwin, etc.
        # Ensures the child process does not terminate when the parent does.
        start_new_session = True

    try:
        process = guarded_proc.popen(
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creation_flags,
            start_new_session=start_new_session,
            close_fds=(platform.system() != "Windows"),
        )
    except FileNotFoundError:
        raise AppFileNotFoundError(command[0], "Command executable") from None
    except OSError as e:
        raise SystemError(f"OS error starting detached process: {e}") from e

    pid = process.pid
    logger.info(f"Successfully started guarded process with PID: {pid}")
    write_pid_to_file(launcher_pid_file_path, pid)
    return pid


def verify_process_identity(
    pid: int,
    expected_executable_path: Optional[str] = None,
    expected_cwd: Optional[str] = None,
    expected_command_args: Optional[Union[str, List[str]]] = None,
):
    """Verifies if a running process matches an expected signature.

    This function checks a process, identified by its `pid`, against one or more
    provided criteria: its executable path, its current working directory (CWD),
    and/or specific command-line arguments. This is useful for confirming that
    a PID read from a file indeed corresponds to the expected application or
    server process, and not some other unrelated process that happens to have
    the same PID if the original process died and its PID was recycled.

    It uses ``psutil.Process(pid).oneshot()`` for efficient information retrieval.
    Path comparisons (for executable and CWD) are case-insensitive and normalized.

    Args:
        pid (int): The Process ID of the process to verify.
        expected_executable_path (Optional[str], optional): The expected absolute
            path of the main executable. Defaults to ``None``.
        expected_cwd (Optional[str], optional): The expected absolute current
            working directory of the process. Defaults to ``None``.
        expected_command_args (Optional[Union[str, List[str]]], optional):
            A specific string or a list of strings that are expected to be present
            in the process's command-line arguments. Defaults to ``None``.

    Raises:
        SystemError: If the ``psutil`` library is not available or if ``psutil``
            encounters an internal error retrieving process information.
        ServerProcessError: If the process with the given `pid` does not exist,
            or if it exists but does not match one or more of the provided
            expected criteria (mismatch details are included in the error message).
        PermissionsError: If ``psutil`` is denied access when trying to get
            information for the specified `pid`.
        MissingArgumentError: If `pid` is not an integer or if none of the
            optional verification criteria (`expected_executable_path`,
            `expected_cwd`, `expected_command_args`) are provided.
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
        proc = psutil.Process(pid)
        # Use oneshot() for performance, as it caches process info for subsequent calls.
        with proc.oneshot():
            proc_name = proc.name()
            proc_exe = proc.exe()
            proc_cwd = proc.cwd()
            proc_cmdline = proc.cmdline()
    except psutil.NoSuchProcess:
        raise ServerProcessError(
            f"Process with PID {pid} does not exist for verification."
        )
    except psutil.AccessDenied:
        raise PermissionsError(f"Access denied when trying to get info for PID {pid}.")
    except psutil.Error as e_psutil:
        raise SystemError(f"Error getting process info for PID {pid}: {e_psutil}.")

    mismatches = []
    # Verify Executable Path
    if expected_executable_path:
        expected_exe_norm = os.path.normcase(os.path.abspath(expected_executable_path))
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

    logger.debug(
        f"Process {pid} (Name: {proc_name}) verified successfully against signature."
    )


def get_verified_bedrock_process(
    server_name: str, server_dir: str, config_dir: str
) -> Optional["psutil.Process"]:
    """Finds, verifies, and returns the Bedrock server process using its PID file.

    This high-level function combines several steps to reliably identify if a
    Bedrock server, identified by `server_name`, is currently running and is indeed
    the correct process. It performs:

        1. Path construction for the server's PID file using
           :func:`get_bedrock_server_pid_file_path`.
        2. Reading the PID from this file via :func:`read_pid_from_file`.
        3. Checking if the process with the read PID is running using :func:`is_process_running`.
        4. If running, verifying the process's identity using :func:`verify_process_identity`.
           The verification checks if the process executable path matches the expected
           ``bedrock_server`` or ``bedrock_server.exe`` in the `server_dir`, and if
           its current working directory is `server_dir`.

    If ``psutil`` is unavailable, this function logs an error and returns ``None``.
    Most other exceptions encountered during the process (e.g., PID file not
    found, process not running, verification mismatch, permissions issues) are
    caught, logged at DEBUG level, and result in ``None`` being returned, as these
    are often considered normal states indicating the server is not running as expected.
    More severe or unexpected errors are logged at ERROR level.

    Args:
        server_name (str): The unique name of the server instance.
        server_dir (str): The server's installation directory, used for verifying
            the executable path and CWD.
        config_dir (str): The main application configuration directory where the
            server's PID file (and its parent subdirectory) are located.

    Returns:
        Optional[psutil.Process]: A ``psutil.Process`` object representing the
        verified, running Bedrock server process if all checks pass. Returns
        ``None`` if ``psutil`` is unavailable, the server is not running, the PID
        file is missing/invalid, or if process verification fails.
    """
    if not PSUTIL_AVAILABLE:
        logger.error("'psutil' is required for this function. Returning None.")
        return None

    # Validate inputs to prevent downstream errors from core functions
    if not isinstance(server_name, str) or not server_name:
        logger.error("get_verified_bedrock_process: server_name is invalid.")
        return None
    if (
        not isinstance(server_dir, str)
        or not server_dir
        or not os.path.isdir(server_dir)
    ):
        logger.error(
            f"get_verified_bedrock_process: server_dir '{server_dir}' is invalid or not a directory."
        )
        return None
    if (
        not isinstance(config_dir, str)
        or not config_dir
        or not os.path.isdir(config_dir)
    ):
        logger.error(
            f"get_verified_bedrock_process: config_dir '{config_dir}' is invalid or not a directory."
        )
        return None

    try:
        pid_file_path = get_bedrock_server_pid_file_path(server_name, config_dir)
        pid = read_pid_from_file(pid_file_path)

        if (
            pid is None
        ):  # Handles both file not found and invalid content from read_pid_from_file
            logger.debug(f"No valid PID found in file for server '{server_name}'.")
            return None

        if not is_process_running(pid):
            logger.debug(
                f"Stale PID {pid} found for '{server_name}'. Process not running."
            )
            # Attempt to clean up stale PID file
            remove_pid_file_if_exists(pid_file_path)
            return None

        # Define the platform-specific executable name to verify against.
        exe_name = (
            "bedrock_server.exe" if platform.system() == "Windows" else "bedrock_server"
        )
        expected_exe_abs = os.path.abspath(os.path.join(server_dir, exe_name))
        expected_cwd_abs = os.path.abspath(server_dir)

        # Verify the running process matches our expectations.
        verify_process_identity(
            pid,
            expected_executable_path=expected_exe_abs,
            expected_cwd=expected_cwd_abs,
        )

        return psutil.Process(pid)

    except (
        AppFileNotFoundError,  # From get_bedrock_server_pid_file_path or verify if paths are bad
        FileOperationError,  # From read_pid_from_file
        ServerProcessError,  # From verify_process_identity
        PermissionsError,  # From verify_process_identity
        MissingArgumentError,  # From called functions if somehow inputs are bad despite checks
    ) as e:
        # These are expected "not running" or "mismatch" scenarios.
        logger.debug(f"Verification failed for server '{server_name}': {e}")
        # Attempt to clean up PID file if verification failed for a running PID
        if "pid" in locals() and pid is not None and os.path.exists(pid_file_path):
            if isinstance(e, ServerProcessError):  # Mismatch
                logger.debug(
                    f"Cleaning up PID file '{pid_file_path}' due to verification mismatch for PID {pid}."
                )
                remove_pid_file_if_exists(pid_file_path)
        return None
    except (
        SystemError,
        Exception,
    ) as e:  # SystemError from psutil functions, or any other unexpected
        # These are more serious, unexpected errors.
        logger.error(
            f"Unexpected error getting verified process for '{server_name}': {e}",
            exc_info=True,
        )
        return None


def terminate_process_by_pid(
    pid: int, terminate_timeout: int = 5, kill_timeout: int = 2
):
    """Attempts to gracefully terminate, then forcefully kill, a process by PID.

    This function implements a two-stage termination strategy:

        1. **Graceful Termination (SIGTERM)**: It first sends a SIGTERM signal
           (``process.terminate()``) to the process with the given `pid`. It then
           waits for `terminate_timeout` seconds for the process to exit cleanly.
        2. **Forceful Kill (SIGKILL)**: If the process does not terminate within
           the `terminate_timeout`, a SIGKILL signal (``process.kill()``) is sent
           to forcibly stop it. It then waits for `kill_timeout` seconds.

    This approach gives the target process a chance to shut down gracefully
    (e.g., save data, release resources) before resorting to a forceful kill.

    Args:
        pid (int): The Process ID of the process to terminate.
        terminate_timeout (int, optional): Seconds to wait for graceful
            termination after SIGTERM. Defaults to 5.
        kill_timeout (int, optional): Seconds to wait for the process to die
            after SIGKILL. Defaults to 2.

    Raises:
        SystemError: If the ``psutil`` library is not available.
        MissingArgumentError: If `pid` is not an integer.
        PermissionsError: If ``psutil`` is denied access when trying to
            terminate the process.
        ServerStopError: For other ``psutil`` errors (e.g., process already
            exited before kill, unexpected errors) or if timeouts are invalid.
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
        process = psutil.Process(pid)
        # 1. Attempt graceful termination first.
        logger.info(f"Attempting graceful termination (SIGTERM) for PID {pid}...")
        process.terminate()
        try:
            process.wait(timeout=terminate_timeout)
            logger.info(f"Process {pid} terminated gracefully.")
            return
        except psutil.TimeoutExpired:
            # 2. If graceful termination fails, resort to forceful killing.
            logger.warning(
                f"Process {pid} did not terminate gracefully within {terminate_timeout}s. Attempting kill (SIGKILL)..."
            )
            process.kill()
            process.wait(timeout=kill_timeout)
            logger.info(f"Process {pid} forcefully killed.")
            return
    except psutil.NoSuchProcess:
        # This is not an error; the process is already gone.
        logger.warning(
            f"Process with PID {pid} disappeared or was already stopped during termination attempt."
        )
    except psutil.AccessDenied:
        raise PermissionsError(
            f"Permission denied trying to terminate process with PID {pid}."
        )
    except Exception as e:
        raise ServerStopError(
            f"Unexpected error terminating process PID {pid}: {e}"
        ) from e


def remove_pid_file_if_exists(pid_file_path: str) -> bool:
    """Removes the specified PID file if it exists, logging outcomes.

    This function checks for the existence of a file at `pid_file_path`.
    If it exists, an attempt is made to delete it. Deletion failures due to
    ``OSError`` (e.g., permission issues) are logged as warnings but do not
    propagate the exception.

    Args:
        pid_file_path (str): The absolute path to the PID file to remove.

    Returns:
        bool: ``True`` if the file was successfully removed or if it did not
        exist initially. ``False`` if an ``OSError`` occurred during an
        attempted removal.

    Raises:
        MissingArgumentError: If `pid_file_path` is not provided or is empty.
    """
    if not isinstance(pid_file_path, str) or not pid_file_path:
        raise MissingArgumentError("PID file path cannot be empty.")

    if os.path.exists(pid_file_path):
        try:
            os.remove(pid_file_path)
            logger.info(f"Removed PID file '{pid_file_path}'.")
            return True
        except OSError as e:
            logger.warning(f"Could not remove PID file '{pid_file_path}': {e}")
            return False
    return True
