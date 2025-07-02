# bedrock_server_manager/core/system/windows.py
"""Provides Windows-specific implementations for system process and service management.

This module offers functionalities tailored for the Windows operating system,
primarily focused on managing Bedrock server processes both in the foreground
and as background Windows Services. It leverages the ``pywin32`` package for
many of its operations, and its availability is checked by the
:const:`PYWIN32_AVAILABLE` flag. Some optional ``pywin32`` modules for cleanup
are checked via :const:`PYWIN32_HAS_OPTIONAL_MODULES`.

Key functionalities include:

Foreground Process Management:

    - Starting a Bedrock server directly in the foreground with IPC capabilities
      (:func:`_windows_start_server`).
    - Sending commands to this foreground server via a named pipe
      (:func:`_windows_send_command`).
    - Stopping the foreground server process using its PID
      (:func:`_windows_stop_server_by_pid`).
    - Internal mechanisms for named pipe server creation, client handling, and
      OS signal management for graceful shutdowns.

Windows Service Management (Requires Administrator Privileges):

    - Checking if a service exists (:func:`check_service_exists`).
    - Creating or updating a Windows Service to run the Bedrock server
      (:func:`create_windows_service`).
    - Enabling (:func:`enable_windows_service`) or disabling
      (:func:`disable_windows_service`) a service.
    - Deleting a service, including cleanup of associated registry entries like
      performance counters and event log sources (:func:`delete_windows_service`).

The module defines constants like :const:`BEDROCK_EXECUTABLE_NAME` and
:const:`PIPE_NAME_TEMPLATE`, and uses global variables such as
:data:`managed_bedrock_servers` and :data:`_foreground_server_shutdown_event`
to manage the state of servers started directly.

Note:
    Functions interacting with the Windows Service Control Manager (SCM)
    typically require Administrator privileges to execute successfully. The module
    attempts to handle :class:`~bedrock_server_manager.error.PermissionsError`
    where appropriate.
"""
import os
import threading
import time
import subprocess
import logging
import signal
import re
from typing import Optional, List, Dict, Any

# Third-party imports. pywin32 is optional but required for IPC.
try:
    import win32pipe
    import win32file
    import win32service
    import win32serviceutil
    import pywintypes

    PYWIN32_AVAILABLE = True
except ImportError:
    PYWIN32_AVAILABLE = False
    win32pipe = None
    win32file = None
    win32service = None
    win32serviceutil = None
    pywintypes = None


try:
    import win32api
    import perfmon
    import win32evtlogutil

    PYWIN32_HAS_OPTIONAL_MODULES = True
except ImportError:
    PYWIN32_HAS_OPTIONAL_MODULES = False
    logging.warning(
        "Optional pywin32 modules (perfmon, win32evtlogutil, win32api) not found. "
        "Some cleanup steps will be skipped."
    )

# Local application imports.
from bedrock_server_manager.core.system import process as core_process
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.error import (
    MissingArgumentError,
    ServerStartError,
    AppFileNotFoundError,
    ServerStopError,
    FileOperationError,
    SystemError,
    SendCommandError,
    ServerNotRunningError,
    PermissionsError,
)

logger = logging.getLogger(__name__)

# --- Constants ---
BEDROCK_EXECUTABLE_NAME = "bedrock_server.exe"
"""The standard filename of the Minecraft Bedrock dedicated server executable on Windows."""

PIPE_NAME_TEMPLATE = r"\\.\pipe\BedrockServerPipe_{server_name}"
"""Template string for creating named pipe names for IPC with foreground servers.
The ``{server_name}`` placeholder will be replaced by a sanitized server name.
Example: ``\\\\.\\pipe\\BedrockServerPipe_MyServer``
"""

# --- Global State Variables ---
managed_bedrock_servers: Dict[str, Dict[str, Any]] = {}
"""A global dictionary to keep track of running foreground server processes and their
associated objects (like the Popen instance, pipe listener thread).
Structure: ``{'server_name': {'process': Popen, 'pipe_thread': Thread, ...}}``
This is primarily used by `_windows_start_server` and its helper threads.
"""

_foreground_server_shutdown_event = threading.Event()
"""A ``threading.Event`` used to signal a shutdown request to all actively managed
foreground server instances (specifically, their main management loops and
pipe listener threads within `_windows_start_server`).
"""

# --- pywin32 Availability Flags ---
# These are set based on imports at the top of the module.
# PYWIN32_AVAILABLE (bool): True if essential pywin32 modules (win32pipe, win32file,
# win32service, pywintypes) were successfully imported. Critical for most of this
# module's functionality.
# PYWIN32_HAS_OPTIONAL_MODULES (bool): True if optional pywin32 modules
# (win32api, perfmon, win32evtlogutil) used for extended cleanup tasks
# (like for `delete_windows_service`) were imported.

# NOTE: All functions in this section require Administrator privileges to interact
# with the Windows Service Control Manager (SCM).


def check_service_exists(service_name: str) -> bool:
    """Checks if a Windows service with the given name exists.

    Requires Administrator privileges for a definitive check, otherwise, it might
    return ``False`` due to access denied errors.

    Args:
        service_name (str): The short name of the service to check (e.g., "MyBedrockServer").

    Returns:
        bool: ``True`` if the service exists, ``False`` otherwise. Returns ``False``
        if ``pywin32`` is not installed or if access is denied (which is logged
        as a warning).

    Raises:
        MissingArgumentError: If `service_name` is empty.
        SystemError: For unexpected Service Control Manager (SCM) errors other
            than "service does not exist" or "access denied".
    """
    if not PYWIN32_AVAILABLE:
        logger.debug("pywin32 not available, check_service_exists returning False.")
        return False
    if not service_name:
        raise MissingArgumentError("Service name cannot be empty.")

    scm_handle = None
    service_handle = None
    try:
        scm_handle = win32service.OpenSCManager(
            None, None, win32service.SC_MANAGER_CONNECT
        )
        service_handle = win32service.OpenService(
            scm_handle, service_name, win32service.SERVICE_QUERY_STATUS
        )
        # If OpenService succeeds, the service exists.
        return True
    except pywintypes.error as e:
        # Error 1060: The specified service does not exist.
        if e.winerror == 1060:
            return False
        # Error 5: Access is denied.
        elif e.winerror == 5:
            logger.warning(
                "Access denied when checking for service '%s'. This check requires Administrator privileges.",
                service_name,
            )
            return False
        else:
            raise SystemError(
                f"Failed to check service '{service_name}': {e.strerror}"
            ) from e
    finally:
        if service_handle:
            win32service.CloseServiceHandle(service_handle)
        if scm_handle:
            win32service.CloseServiceHandle(scm_handle)


def create_windows_service(
    service_name: str,
    display_name: str,
    description: str,
    command: str,
) -> None:
    """Creates a new Windows service or updates an existing one.

    This function interacts with the Windows Service Control Manager (SCM) to
    either create a new service or modify the configuration of an existing
    service (specifically its display name, description, and executable command).
    The service is configured for automatic start (``SERVICE_AUTO_START``) and
    runs as ``LocalSystem`` by default upon creation.

    Requires Administrator privileges.

    Args:
        service_name (str): The short, unique name for the service
            (e.g., "MyBedrockServerSvc").
        display_name (str): The user-friendly name shown in the Services console
            (e.g., "My Bedrock Server").
        description (str): A detailed description of the service.
        command (str): The full command line to execute for the service,
            including the path to the executable and any arguments.
            Example: ``"C:\\path\\to\\python.exe C:\\path\\to\\script.py --run-as-service"``

    Raises:
        SystemError: If ``pywin32`` is not available, or for other unexpected
            SCM errors during service creation/update.
        MissingArgumentError: If any of the required string arguments
            (`service_name`, `display_name`, `description`, `command`) are empty.
        PermissionsError: If the operation fails due to insufficient privileges
            (typically requires Administrator rights).
    """
    if not PYWIN32_AVAILABLE:
        raise SystemError("pywin32 is required to manage Windows services.")
    if not all([service_name, display_name, description, command]):
        raise MissingArgumentError(
            "service_name, display_name, description, and command are required."
        )

    logger.info(f"Attempting to create/update Windows service '{service_name}'...")

    scm_handle = None
    service_handle = None
    try:
        scm_handle = win32service.OpenSCManager(
            None, None, win32service.SC_MANAGER_ALL_ACCESS
        )

        service_exists = check_service_exists(service_name)

        if not service_exists:
            logger.info(f"Service '{service_name}' does not exist. Creating...")
            # When creating, we can rely on defaults for the service account (LocalSystem)
            service_handle = win32service.CreateService(
                scm_handle,
                service_name,
                display_name,
                win32service.SERVICE_ALL_ACCESS,
                win32service.SERVICE_WIN32_OWN_PROCESS,
                win32service.SERVICE_AUTO_START,
                win32service.SERVICE_ERROR_NORMAL,
                command,
                None,
                0,
                None,
                None,
                None,
            )
            logger.info(f"Service '{service_name}' created successfully.")
        else:
            logger.info(f"Service '{service_name}' already exists. Updating...")
            service_handle = win32service.OpenService(
                scm_handle, service_name, win32service.SERVICE_ALL_ACCESS
            )

            win32service.ChangeServiceConfig(
                service_handle,
                win32service.SERVICE_NO_CHANGE,  # ServiceType
                win32service.SERVICE_NO_CHANGE,  # StartType
                win32service.SERVICE_NO_CHANGE,  # ErrorControl
                command,  # BinaryPathName
                None,  # LoadOrderGroup
                0,  # TagId
                None,  # Dependencies
                None,  # ServiceStartName
                None,  # Password
                display_name,  # DisplayName
            )
            logger.info(f"Service '{service_name}' command and display name updated.")

        # Set or update the service description (this part was already correct)
        win32service.ChangeServiceConfig2(
            service_handle, win32service.SERVICE_CONFIG_DESCRIPTION, description
        )
        logger.info(f"Service '{service_name}' description updated.")

    except pywintypes.error as e:
        if e.winerror == 5:
            raise PermissionsError(
                f"Failed to create/update service '{service_name}'. This operation requires Administrator privileges."
            ) from e
        # Check for error 1057 specifically
        elif e.winerror == 1057:
            raise SystemError(
                f"Failed to update service '{service_name}': {e.strerror}. This can happen if the service account is misconfigured."
            ) from e
        else:
            raise SystemError(
                f"Failed to create/update service '{service_name}': {e.strerror}"
            ) from e
    finally:
        if service_handle:
            win32service.CloseServiceHandle(service_handle)
        if scm_handle:
            win32service.CloseServiceHandle(scm_handle)


def enable_windows_service(service_name: str) -> None:
    """Enables a Windows service by setting its start type to 'Automatic'.

    This function interacts with the Windows Service Control Manager (SCM)
    to change the start type of the specified service to ``SERVICE_AUTO_START``.

    Requires Administrator privileges.

    Args:
        service_name (str): The short name of the service to enable.

    Raises:
        SystemError: If ``pywin32`` is not available, if the service does not
            exist, or for other unexpected SCM errors.
        MissingArgumentError: If `service_name` is empty.
        PermissionsError: If the operation fails due to insufficient privileges.
    """
    if not PYWIN32_AVAILABLE:
        raise SystemError("pywin32 is required to manage Windows services.")
    if not service_name:
        raise MissingArgumentError("Service name cannot be empty.")

    logger.info(f"Enabling service '{service_name}' (setting to Automatic start)...")
    scm_handle = None
    service_handle = None
    try:
        scm_handle = win32service.OpenSCManager(
            None, None, win32service.SC_MANAGER_CONNECT
        )
        service_handle = win32service.OpenService(
            scm_handle, service_name, win32service.SERVICE_CHANGE_CONFIG
        )

        win32service.ChangeServiceConfig(
            service_handle,
            win32service.SERVICE_NO_CHANGE,
            win32service.SERVICE_AUTO_START,  # Set to Automatic
            win32service.SERVICE_NO_CHANGE,
            None,
            None,
            0,
            None,
            None,
            None,
            None,
        )
        logger.info(f"Service '{service_name}' enabled successfully.")
    except pywintypes.error as e:
        if e.winerror == 5:
            raise PermissionsError(
                f"Failed to enable service '{service_name}'. Administrator privileges required."
            ) from e
        elif e.winerror == 1060:
            raise SystemError(
                f"Cannot enable: Service '{service_name}' not found."
            ) from e
        else:
            raise SystemError(
                f"Failed to enable service '{service_name}': {e.strerror}"
            ) from e
    finally:
        if service_handle:
            win32service.CloseServiceHandle(service_handle)
        if scm_handle:
            win32service.CloseServiceHandle(scm_handle)


def disable_windows_service(service_name: str) -> None:
    """Disables a Windows service by setting its start type to 'Disabled'.

    This function interacts with the Windows Service Control Manager (SCM)
    to change the start type of the specified service to ``SERVICE_DISABLED``.
    If the service does not exist, a warning is logged, and the function returns
    gracefully.

    Requires Administrator privileges.

    Args:
        service_name (str): The short name of the service to disable.

    Raises:
        SystemError: If ``pywin32`` is not available or for unexpected SCM errors
            (other than service not existing).
        MissingArgumentError: If `service_name` is empty.
        PermissionsError: If the operation fails due to insufficient privileges.
    """
    if not PYWIN32_AVAILABLE:
        raise SystemError("pywin32 is required to manage Windows services.")
    if not service_name:
        raise MissingArgumentError("Service name cannot be empty.")

    logger.info(f"Disabling service '{service_name}'...")
    scm_handle = None
    service_handle = None
    try:
        scm_handle = win32service.OpenSCManager(
            None, None, win32service.SC_MANAGER_CONNECT
        )
        service_handle = win32service.OpenService(
            scm_handle, service_name, win32service.SERVICE_CHANGE_CONFIG
        )
        win32service.ChangeServiceConfig(
            service_handle,
            win32service.SERVICE_NO_CHANGE,
            win32service.SERVICE_DISABLED,  # Set to Disabled
            win32service.SERVICE_NO_CHANGE,
            None,
            None,
            0,
            None,
            None,
            None,
            None,
        )
        logger.info(f"Service '{service_name}' disabled successfully.")
    except pywintypes.error as e:
        if e.winerror == 5:
            raise PermissionsError(
                f"Failed to disable service '{service_name}'. Administrator privileges required."
            ) from e
        elif e.winerror == 1060:
            logger.warning(
                "Attempted to disable service '%s', but it does not exist.",
                service_name,
            )
            return
        else:
            raise SystemError(
                f"Failed to disable service '{service_name}': {e.strerror}"
            ) from e
    finally:
        if service_handle:
            win32service.CloseServiceHandle(service_handle)
        if scm_handle:
            win32service.CloseServiceHandle(scm_handle)


def delete_windows_service(service_name: str) -> None:
    """Deletes a Windows service and performs associated cleanup.

    This function interacts with the Windows Service Control Manager (SCM) to
    delete the specified service. It also attempts to perform cleanup operations
    such as unloading performance counters and removing event log sources from
    the registry, provided that optional ``pywin32`` modules (like ``perfmon``
    and ``win32evtlogutil``) are available (checked by
    :const:`PYWIN32_HAS_OPTIONAL_MODULES`).

    The service should ideally be stopped before deletion, though this function
    does not explicitly stop it. If the service does not exist or is already
    marked for deletion, warnings are logged, and the function may proceed with
    cleanup or return gracefully.

    Requires Administrator privileges.

    Args:
        service_name (str): The short name of the service to delete.

    Raises:
        SystemError: If ``pywin32`` is not available or for critical SCM errors
            during deletion (e.g., service cannot be deleted for reasons other
            than access denied, not existing, or already marked for deletion).
        MissingArgumentError: If `service_name` is empty.
        PermissionsError: If the operation fails due to insufficient privileges.
    """
    if not PYWIN32_AVAILABLE:
        raise SystemError("pywin32 is required to manage Windows services.")
    if not service_name:
        raise MissingArgumentError("Service name cannot be empty.")

    logger.info(f"Attempting to delete service '{service_name}' and perform cleanup...")

    # --- Step 1: Unload Performance Counters (Optional Cleanup) ---
    if PYWIN32_HAS_OPTIONAL_MODULES:
        try:
            # Service performance counters are often registered with a specific name,
            # which might be 'python.exe <service_name>' as shown in the reference.
            # Adjust if your service uses a different registration name.
            perfmon.UnloadPerfCounterTextStrings("python.exe " + service_name)
            logger.info(f"Unloaded performance counter strings for '{service_name}'.")
        except (AttributeError, pywintypes.error, Exception) as e:
            # AttributeError if perfmon is missing expected function, pywintypes.error for Win32 errors
            logger.warning(f"Failed to unload perf counters for '{service_name}': {e}")
        except ImportError:
            # This block might be redundant if PYWIN32_HAS_OPTIONAL_MODULES handles it,
            # but good for safety if perfmon itself is missing specific components.
            logger.warning("perfmon module not fully available for counter cleanup.")
    else:
        logger.info(
            "Skipping performance counter cleanup (optional pywin32 modules not found)."
        )

    # --- Step 2: Delete the Windows Service ---
    scm_handle = None
    service_handle = None
    try:
        # Open Service Control Manager with all access rights
        scm_handle = win32service.OpenSCManager(
            None, None, win32service.SC_MANAGER_ALL_ACCESS
        )
        # Open the specific service with SERVICE_ALL_ACCESS to allow deletion
        # and potentially other operations if needed (e.g., stopping).
        service_handle = win32service.OpenService(
            scm_handle, service_name, win32service.SERVICE_ALL_ACCESS
        )
        win32service.DeleteService(service_handle)
        logger.info(f"Service '{service_name}' deleted successfully.")
    except pywintypes.error as e:
        if e.winerror == 5:  # Access is denied
            raise PermissionsError(
                f"Failed to delete service '{service_name}'. Administrator privileges required."
            ) from e
        elif e.winerror == 1060:  # The specified service does not exist.
            logger.warning(
                "Attempted to delete service '%s', but it does not exist.", service_name
            )
            return  # Exit early if service doesn't exist, no more cleanup needed for it
        elif e.winerror == 1072:  # The specified service has been marked for deletion.
            logger.info(
                f"Service '{service_name}' was already marked for deletion. Continuing with cleanup."
            )
            # Do not return here, continue to cleanup other aspects
        else:
            raise SystemError(
                f"Failed to delete service '{service_name}': {e.strerror}. "
                "Ensure the service is stopped before deletion."
            ) from e
    finally:
        # Ensure service handles are closed to prevent resource leaks
        if service_handle:
            win32service.CloseServiceHandle(service_handle)
        if scm_handle:
            win32service.CloseServiceHandle(scm_handle)

    # --- Step 3: Remove Event Log Source (Optional Cleanup) ---
    if PYWIN32_HAS_OPTIONAL_MODULES:
        try:
            win32evtlogutil.RemoveSourceFromRegistry(service_name)
            logger.info(f"Removed event log source for '{service_name}' from registry.")
        except (AttributeError, pywintypes.error, Exception) as e:
            # AttributeError if win32evtlogutil is missing expected function, pywintypes.error for Win32 errors
            logger.warning(
                f"Failed to remove event log source for '{service_name}': {e}"
            )
        except ImportError:
            # Safety check if win32evtlogutil itself is missing specific components
            logger.warning(
                "win32evtlogutil module not fully available for event log cleanup."
            )
    else:
        logger.info(
            "Skipping event log source cleanup (optional pywin32 modules not found)."
        )


# --- FOREGROUND SERVER MANAGEMENT ---


def _handle_os_signals(sig: int, frame: Any):
    """Signal handler for SIGINT (Ctrl+C) to initiate graceful shutdown.

    This function is registered as the handler for `signal.SIGINT`. When the
    signal is received, it sets the global `_foreground_server_shutdown_event`,
    which is monitored by the main loop in `_windows_start_server` to begin
    the shutdown sequence.

    Args:
        sig (int): The signal number.
        frame (Any): The current stack frame (unused).
    """
    logger.info(f"OS Signal {sig} received. Setting foreground shutdown event.")
    _foreground_server_shutdown_event.set()


def _handle_individual_pipe_client(
    pipe_handle: Any, bedrock_process: subprocess.Popen, server_name_for_log: str
):
    """Handles I/O for a single connected named pipe client in a dedicated thread.

    This function is executed in a new thread for each client that connects to
    the named pipe server managed by `_main_pipe_server_listener_thread`.
    It continuously reads data (commands) sent by the client through the pipe,
    decodes it, and writes it to the standard input of the `bedrock_process`.
    The loop continues until the client disconnects, an error occurs, or the
    Bedrock server process terminates.

    Args:
        pipe_handle (Any): The handle to the connected named pipe instance for this
            specific client (typically a `pywintypes.HANDLE` or similar).
        bedrock_process (subprocess.Popen): The `subprocess.Popen` object representing
            the running Bedrock server. This is used to send commands to its stdin
            and to check if it's still running.
        server_name_for_log (str): The name of the server this pipe client is
            associated with, used for logging purposes.
    """
    client_thread_name = threading.current_thread().name
    client_info = (
        f"client for server '{server_name_for_log}' (Handler {client_thread_name})"
    )
    logger.info(f"PIPE_CLIENT_HANDLER: Entered for {client_info}.")

    if not all([PYWIN32_AVAILABLE, win32file, bedrock_process]):
        logger.error(
            f"PIPE_CLIENT_HANDLER: Pre-requisites not met for {client_info}. Exiting."
        )
        if pipe_handle:
            try:
                win32file.CloseHandle(pipe_handle)
            except (pywintypes.error, AttributeError):
                pass
        return

    try:
        # Loop to read data as long as the server process is running.
        while bedrock_process.poll() is None:
            logger.debug(f"PIPE_CLIENT_HANDLER: Waiting for data from {client_info}...")
            hr, data_read = win32file.ReadFile(pipe_handle, 65535)

            if bedrock_process.poll() is not None:
                break

            if hr == 0:  # Read success.
                command_str = data_read.decode("utf-8").strip()
                if not command_str:
                    logger.info(
                        f"PIPE_CLIENT_HANDLER: Client disconnected gracefully from {client_info}."
                    )
                    break

                logger.info(
                    f"PIPE_CLIENT_HANDLER: Received command from {client_info}: '{command_str}'"
                )
                try:
                    # Forward the command to the Bedrock server's stdin.
                    if bedrock_process.stdin and not bedrock_process.stdin.closed:
                        bedrock_process.stdin.write(
                            (command_str + "\n").encode("utf-8")
                        )
                        bedrock_process.stdin.flush()
                    else:
                        logger.warning(
                            f"PIPE_CLIENT_HANDLER: Stdin for server '{server_name_for_log}' is closed."
                        )
                        break
                except (OSError, ValueError) as e_write:
                    logger.error(
                        f"PIPE_CLIENT_HANDLER: Error writing to stdin for '{server_name_for_log}': {e_write}."
                    )
                    break
            elif hr == 109:  # ERROR_BROKEN_PIPE
                logger.info(
                    f"PIPE_CLIENT_HANDLER: Pipe broken for {client_info}. Client disconnected."
                )
                break
            else:
                logger.error(
                    f"PIPE_CLIENT_HANDLER: Pipe ReadFile error for {client_info}, hr: {hr}. Closing."
                )
                break
    except pywintypes.error as e_pywin:
        if e_pywin.winerror in (109, 233):  # Broken pipe or not connected.
            logger.info(
                f"PIPE_CLIENT_HANDLER: Pipe for {client_info} closed (winerror {e_pywin.winerror})."
            )
        else:
            logger.error(
                f"PIPE_CLIENT_HANDLER: pywintypes.error for {client_info}: {e_pywin}",
                exc_info=True,
            )
    except Exception as e_unexp:
        logger.error(
            f"PIPE_CLIENT_HANDLER: Unexpected error for {client_info}: {e_unexp}",
            exc_info=True,
        )
    finally:
        # Ensure the pipe handle is properly closed.
        if all([PYWIN32_AVAILABLE, win32pipe, win32file, pipe_handle]):
            try:
                win32pipe.DisconnectNamedPipe(pipe_handle)
            except (pywintypes.error, AttributeError):
                pass
            try:
                win32file.CloseHandle(pipe_handle)
            except (pywintypes.error, AttributeError):
                pass
        logger.info(f"PIPE_CLIENT_HANDLER: Finished for {client_info}.")


def _main_pipe_server_listener_thread(
    pipe_name: str,
    bedrock_process: subprocess.Popen,
    server_name: str,
    overall_shutdown_event: threading.Event,
):
    """Main listener thread for the named pipe server, handling client connections.

    This function runs in a dedicated thread when a Bedrock server is started
    in the foreground via `_windows_start_server`. Its primary responsibility
    is to create named pipe instances using `win32pipe.CreateNamedPipe` and
    wait for client connections using `win32pipe.ConnectNamedPipe`.

    Upon a successful client connection, it spawns a new daemon thread running
    `_handle_individual_pipe_client` to manage I/O for that specific client.
    This allows the main listener to immediately go back to waiting for new
    connections, enabling multiple clients to interact with the server
    concurrently via the named pipe.

    The listener loop continues as long as the `overall_shutdown_event` is not
    set and the `bedrock_process` is still running. If the shutdown event is
    triggered or the server process terminates, the listener thread will exit.

    Args:
        pipe_name (str): The full name of the pipe to create and listen on
            (e.g., ``\\\\.\\pipe\\BedrockServerPipe_MyServer``).
        bedrock_process (subprocess.Popen): The `subprocess.Popen` object for the
            Bedrock server. Used to check if the server is still running.
        server_name (str): The name of the server, used for logging purposes.
        overall_shutdown_event (threading.Event): A `threading.Event` object that
            signals this listener thread to terminate its loop and exit.
    """
    logger.info(f"MAIN_PIPE_LISTENER: Starting for pipe '{pipe_name}'.")

    if not all([PYWIN32_AVAILABLE, win32pipe, win32file, bedrock_process]):
        logger.error("MAIN_PIPE_LISTENER: Pre-requisites not met. Exiting.")
        overall_shutdown_event.set()
        return

    while not overall_shutdown_event.is_set() and bedrock_process.poll() is None:
        pipe_instance_handle = None
        try:
            # Create a new instance of the named pipe.
            pipe_instance_handle = win32pipe.CreateNamedPipe(
                pipe_name,
                win32pipe.PIPE_ACCESS_DUPLEX,
                win32pipe.PIPE_TYPE_MESSAGE
                | win32pipe.PIPE_READMODE_MESSAGE
                | win32pipe.PIPE_WAIT,
                win32pipe.PIPE_UNLIMITED_INSTANCES,
                65536,
                65536,
                0,
                None,
            )
            logger.info(
                f"MAIN_PIPE_LISTENER: Pipe instance created. Waiting for client..."
            )
            # Block until a client connects.
            win32pipe.ConnectNamedPipe(pipe_instance_handle, None)

            if overall_shutdown_event.is_set():
                break

            # Spawn a new thread to handle the connected client.
            logger.info(
                f"MAIN_PIPE_LISTENER: Client connected. Spawning handler thread."
            )
            client_handler_thread = threading.Thread(
                target=_handle_individual_pipe_client,
                args=(pipe_instance_handle, bedrock_process, server_name),
                daemon=True,
            )
            client_handler_thread.start()
            pipe_instance_handle = None  # The handler thread now owns the handle.
        except pywintypes.error as e:
            if overall_shutdown_event.is_set():
                break
            if e.winerror == 231:  # All pipes busy
                time.sleep(0.1)
            elif e.winerror == 2:  # Cannot create pipe
                logger.error(
                    f"MAIN_PIPE_LISTENER: Pipe '{pipe_name}' could not be created. Shutting down."
                )
                overall_shutdown_event.set()
            else:
                logger.warning(
                    f"MAIN_PIPE_LISTENER: pywintypes.error in main loop (winerror {e.winerror}): {e}"
                )
                time.sleep(0.5)
        except Exception as e:
            if overall_shutdown_event.is_set():
                break
            logger.error(f"MAIN_PIPE_LISTENER: Unexpected error: {e}", exc_info=True)
            time.sleep(1)
        finally:
            # Clean up the handle if it wasn't passed to a handler thread.
            if pipe_instance_handle and all([PYWIN32_AVAILABLE, win32file]):
                try:
                    win32file.CloseHandle(pipe_instance_handle)
                except (pywintypes.error, AttributeError):
                    pass

    logger.info(
        f"MAIN_PIPE_LISTENER: Main pipe listener thread for '{pipe_name}' has EXITED."
    )


def _windows_start_server(server_name: str, server_dir: str, config_dir: str) -> None:
    """Starts a Bedrock server in the foreground and manages its lifecycle on Windows.

    This function is intended to be run as the main blocking process when
    starting a server directly (not as a service). It performs the following:

        1. Checks if `pywin32` is available (required for named pipe IPC).
        2. Verifies that another instance of the same server isn't already running
           by checking PID files and process status. Cleans up stale PID files.
        3. Sets up an OS signal handler for `SIGINT` (Ctrl+C) to trigger graceful shutdown.
        4. Launches the Bedrock server executable (`bedrock_server.exe`) as a subprocess,
           redirecting its stdout/stderr to `server_output.txt` in the server directory.
        5. Writes the new server process's PID to a ``<server_name>.pid`` file.
        6. Starts a named pipe server listener thread (`_main_pipe_server_listener_thread`)
           to accept commands for the Bedrock server. The pipe name is derived from
           `server_name`.
        7. Enters a blocking loop, waiting for the `_foreground_server_shutdown_event`
           to be set (e.g., by Ctrl+C or if the server process dies).
        8. Upon shutdown, attempts to gracefully stop the Bedrock server by sending
           the "stop" command via its stdin, then waits for it to terminate. If it
           doesn't stop in time, it's forcibly terminated.
        9. Cleans up the PID file, closes handles, and restores the original SIGINT handler.

    Args:
        server_name (str): The unique name identifier for the server.
        server_dir (str): The absolute path to the server's installation directory,
            where `bedrock_server.exe` is located.
        config_dir (str): The absolute path to the application's configuration
            directory, used for storing the PID file.

    Raises:
        SystemError: If the `pywin32` package is not installed (required for IPC).
        MissingArgumentError: If `server_name`, `server_dir`, or `config_dir` are empty.
        ServerStartError: If the server appears to be already running, or if any
            critical step in launching the server or its IPC mechanism fails.
        AppFileNotFoundError: If `bedrock_server.exe` is not found in `server_dir`.
    """
    if not PYWIN32_AVAILABLE:
        raise SystemError(
            "The 'pywin32' package is required for Windows named pipe functionality."
        )
    if not all([server_name, server_dir, config_dir]):
        raise MissingArgumentError(
            "server_name, server_dir, and config_dir are required."
        )

    logger.info(
        f"Starting server '{server_name}' in FOREGROUND blocking mode (Windows)..."
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

    output_file = os.path.join(server_dir, "server_output.txt")

    # Set up a signal handler to catch Ctrl+C.
    original_sigint_handler = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, _handle_os_signals)

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
            stdin=subprocess.PIPE,
            stdout=server_stdout_handle,
            stderr=subprocess.STDOUT,
            text=False,
            bufsize=0,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        logger.info(
            f"Bedrock Server '{server_name}' started with PID: {bedrock_process.pid}."
        )

        # --- Manage PID and Pipe ---
        # Write the new process ID to the PID file.
        server_pid_file_path = core_process.get_bedrock_server_pid_file_path(
            server_name, config_dir
        )
        core_process.write_pid_to_file(server_pid_file_path, bedrock_process.pid)

        # Start the listener thread for the named pipe.
        pipe_name = PIPE_NAME_TEMPLATE.format(
            server_name=re.sub(r"\W+", "_", server_name)
        )
        main_pipe_listener_thread_obj = threading.Thread(
            target=_main_pipe_server_listener_thread,
            args=(
                pipe_name,
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
            f"Failed to start server '{server_name}': {e_start}"
        ) from e_start
    finally:
        # --- Cleanup ---
        # This block ensures resources are cleaned up on shutdown.
        logger.info(f"Initiating cleanup for wrapper of '{server_name}'...")
        _foreground_server_shutdown_event.set()

        if main_pipe_listener_thread_obj and main_pipe_listener_thread_obj.is_alive():
            main_pipe_listener_thread_obj.join(timeout=3.0)

        # Gracefully stop the Bedrock server process if it's still running.
        if bedrock_process and bedrock_process.poll() is None:
            logger.info(f"Sending 'stop' command to Bedrock server '{server_name}'.")
            try:
                if bedrock_process.stdin and not bedrock_process.stdin.closed:
                    bedrock_process.stdin.write(b"stop\r\n")
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

        # Clean up the PID file.
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

        if server_name in managed_bedrock_servers:
            del managed_bedrock_servers[server_name]

        signal.signal(signal.SIGINT, original_sigint_handler)
        logger.info(f"Cleanup for server '{server_name}' finished.")


def _windows_send_command(server_name: str, command: str) -> None:
    """Sends a command to a running Bedrock server via its named pipe.

    This function connects to the named pipe associated with the specified
    `server_name` (the pipe name is derived using :const:`PIPE_NAME_TEMPLATE`).
    It then writes the given `command` string (UTF-8 encoded, with a newline)
    to the pipe, which should be received by the server's pipe listener
    (specifically, :func:`_handle_individual_pipe_client` which forwards it to
    the Bedrock server's stdin).

    Args:
        server_name (str): The name of the server to send the command to.
        command (str): The command string to send (e.g., "list", "say Hello").

    Raises:
        SystemError: If the `pywin32` module is not installed.
        MissingArgumentError: If `server_name` or `command` is empty.
        ServerNotRunningError: If the named pipe for the server does not exist
            (typically means the server or its pipe listener is not running).
        SendCommandError: If connecting to or writing to the pipe fails for
            other reasons (e.g., Windows errors).
    """
    if not PYWIN32_AVAILABLE:
        raise SystemError("Cannot send command: 'pywin32' module not found.")
    if not all([server_name, command]):
        raise MissingArgumentError("server_name and command cannot be empty.")

    pipe_name = PIPE_NAME_TEMPLATE.format(server_name=re.sub(r"\W+", "_", server_name))
    handle = None
    try:
        # Connect to the existing named pipe.
        handle = win32file.CreateFile(
            pipe_name,
            win32file.GENERIC_WRITE,
            0,
            None,
            win32file.OPEN_EXISTING,
            0,
            None,
        )
        win32pipe.SetNamedPipeHandleState(
            handle, win32pipe.PIPE_READMODE_MESSAGE, None, None
        )
        # Write the command to the pipe.
        win32file.WriteFile(handle, (command + "\r\n").encode("utf-8"))
        logger.info(f"Sent command '{command}' to server '{server_name}'.")
    except pywintypes.error as e:
        if e.winerror == 2:  # ERROR_FILE_NOT_FOUND
            raise ServerNotRunningError(
                f"Pipe '{pipe_name}' not found. Server likely not running."
            ) from e
        else:
            raise SendCommandError(
                f"Windows error sending command via '{pipe_name}': {e.strerror}"
            ) from e
    except Exception as e:
        raise SendCommandError(
            f"Unexpected error sending command via pipe '{pipe_name}': {e}"
        ) from e
    finally:
        # Ensure the handle is closed.
        if handle and all([PYWIN32_AVAILABLE, win32file]):
            try:
                win32file.CloseHandle(handle)
            except (pywintypes.error, AttributeError):
                pass


def _windows_stop_server_by_pid(server_name: str, config_dir: str) -> None:
    """Stops a Bedrock server process on Windows using its PID file.

    This function attempts to stop a Bedrock server that was presumably started
    in the foreground (e.g., via :func:`_windows_start_server`). It performs
    the following steps:

        1. Constructs the path to the server's PID file (e.g., ``<server_name>.pid``)
           within the specified `config_dir`.
        2. Reads the PID from this file using :func:`core_process.read_pid_from_file`.
        3. If no PID file is found or no PID is read, it assumes the server is not
           running and returns.
        4. Checks if the process with the read PID is actually running using
           :func:`core_process.is_process_running`. If not, it cleans up the stale
           PID file and returns.
        5. If the process is running, it terminates the process using
           :func:`core_process.terminate_process_by_pid`.
        6. Cleans up the PID file after successful termination.

    Args:
        server_name (str): The name of the server to stop. This is used to
            determine the PID file name.
        config_dir (str): The application's configuration directory where the
            PID file is expected to be located.

    Raises:
        MissingArgumentError: If `server_name` or `config_dir` are empty.
        ServerStopError: If reading the PID file fails (other than not found),
            or if terminating the process via PID fails. This typically wraps
            underlying ``FileOperationError`` or ``SystemError`` from the
            ``core_process`` module.
    """
    if not all([server_name, config_dir]):
        raise MissingArgumentError("server_name and config_dir are required.")

    logger.info(f"Attempting to stop server '{server_name}' by PID on Windows...")

    try:
        pid_file_path = core_process.get_bedrock_server_pid_file_path(
            server_name, config_dir
        )
        pid_to_stop = core_process.read_pid_from_file(pid_file_path)

        if pid_to_stop is None:
            logger.info(
                f"No PID file for '{server_name}'. Assuming server is not running."
            )
            return

        if not core_process.is_process_running(pid_to_stop):
            logger.warning(
                f"Stale PID {pid_to_stop} found for '{server_name}'. Removing PID file."
            )
            core_process.remove_pid_file_if_exists(pid_file_path)
            return

        # If the process is running, terminate it.
        logger.info(
            f"Found running server '{server_name}' with PID {pid_to_stop}. Terminating..."
        )
        core_process.terminate_process_by_pid(pid_to_stop)

        # Clean up the PID file after successful termination.
        core_process.remove_pid_file_if_exists(pid_file_path)
        logger.info(
            f"Stop sequence for server '{server_name}' (PID {pid_to_stop}) completed."
        )

    except (AppFileNotFoundError, FileOperationError):
        logger.info(
            f"Could not find or read PID file for '{server_name}'. Assuming it's already stopped."
        )
    except (ServerStopError, SystemError) as e:
        # Re-raise as a ServerStopError to signal failure to the caller.
        raise ServerStopError(f"Failed to stop server '{server_name}': {e}") from e
