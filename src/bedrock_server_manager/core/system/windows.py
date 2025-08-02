# bedrock_server_manager/core/system/windows.py
"""Provides Windows-specific implementations for system service management.

This module offers functionalities tailored for the Windows operating system,
primarily focused on managing Windows Services. It leverages the ``pywin32`` package for
many of its operations, and its availability is checked by the
:const:`PYWIN32_AVAILABLE` flag. Some optional ``pywin32`` modules for cleanup
are checked via :const:`PYWIN32_HAS_OPTIONAL_MODULES`.

Key functionalities include:


Windows Service Management (Requires Administrator Privileges):

    - Checking if a service exists (:func:`check_service_exists`).
    - Creating or updating a Windows Service to run the Bedrock server
      (:func:`create_windows_service`).
    - Enabling (:func:`enable_windows_service`) or disabling
      (:func:`disable_windows_service`) a service.
    - Deleting a service, including cleanup of associated registry entries like
      performance counters and event log sources (:func:`delete_windows_service`).

Note:
    Functions interacting with the Windows Service Control Manager (SCM)
    typically require Administrator privileges to execute successfully. The module
    attempts to handle :class:`~bedrock_server_manager.error.PermissionsError`
    where appropriate.
"""
import logging
from typing import Optional

# Third-party imports. pywin32 is optional but required for IPC.
try:
    import win32pipe
    import win32file
    import win32service
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
    import perfmon
    import win32evtlogutil

    PYWIN32_HAS_OPTIONAL_MODULES = True
except ImportError:
    PYWIN32_HAS_OPTIONAL_MODULES = False

# Local application imports.
from ...error import (
    MissingArgumentError,
    SystemError,
    PermissionsError,
)

logger = logging.getLogger(__name__)

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
    username: Optional[str] = None,
    password: Optional[str] = None,
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
        username (Optional[str], optional): The username to run the service as.
            If ``None``, the service runs as ``LocalSystem``. Defaults to ``None``.
        password (Optional[str], optional): The password for the user.
            Required if `username` is provided. Defaults to ``None``.

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
                f".\\{username}" if username else None,
                password,
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
                f".\\{username}" if username else None,  # ServiceStartName
                password,  # Password
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
