# bedrock_server_manager/api/web.py
"""Provides API functions for managing the application's own web user interface.

This module contains the logic for controlling the lifecycle and querying the
status of the built-in web UI, which is powered by FastAPI. It interfaces with the
:class:`~bedrock_server_manager.core.manager.BedrockServerManager` to handle:

    - Starting the web server in 'direct' (blocking) or 'detached' (background) modes
      (:func:`~.start_web_server_api`).
    - Stopping the detached web server process (:func:`~.stop_web_server_api`).
    - Checking the runtime status of the web server (:func:`~.get_web_server_status_api`).
    - Managing the system service for the Web UI (create, enable, disable, remove, get status)
      via functions like :func:`~.create_web_ui_service` and :func:`~.get_web_ui_service_status`.

These functions are intended for programmatic control of the application's web server,
often used by CLI commands or service management scripts.
"""
import logging
from typing import Dict, Optional, Any, List, Union
import os

try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

# Plugin system imports to bridge API functionality.
from ..plugins import plugin_method

# Local application imports.
from ..core.system import process as system_process_utils
from ..error import (
    BSMError,
    FileOperationError,
    ServerProcessError,
    SystemError,
    UserInputError,
)
from ..context import AppContext

logger = logging.getLogger(__name__)


from ..plugins.event_trigger import trigger_plugin_event


@trigger_plugin_event(before="before_web_server_start", after="after_web_server_start")
def start_web_server_api(
    app_context: AppContext,
    host: str = None,
    port: Optional[int] = None,
    debug: bool = False,
    mode: str = "direct",
    threads: Optional[int] = None,
) -> Dict[str, Any]:
    """Starts the application's web server.

    This function can start the web server in two modes:
        - 'direct': A blocking call that runs the server in the current process
          Useful for development or when managed by an external process manager.
        - 'detached': Launches the server as a new background process and creates
          a PID file to track it. Requires the `psutil` library. Uses various
          methods from :class:`~bedrock_server_manager.core.manager.BedrockServerManager`
          and :mod:`~bedrock_server_manager.core.system.process` for process management.

    Triggers ``before_web_server_start`` and ``after_web_server_start`` plugin events.

    Args:
        host (Optional[str], optional): The host address
            to bind the web server to.
            If ``None``, defaults to the application's configured setting (typically "127.0.0.1").
            Defaults to ``None``.
        debug (bool, optional): If ``True``, starts the web server (Uvicorn) in
            debug mode (e.g., with auto-reload). Defaults to ``False``.
        mode (str, optional): The start mode, either 'direct' or 'detached'.
            Defaults to 'direct'.
        threads (Optional[int]): Specifies the number of worker processes for Uvicorn

            Only used for Windows Service

    Returns:
        Dict[str, Any]: A dictionary with the operation result.
        If 'direct' mode: ``{"status": "success", "message": "Web server (direct mode) shut down."}``
        If 'detached' mode (success): ``{"status": "success", "pid": <pid>, "message": "Web server started (PID: <pid>)."}``
        On error: ``{"status": "error", "message": "<error_message>"}``.

    Raises:
        UserInputError: If the provided `mode` is invalid.
        SystemError: If `detached` mode is used but `psutil` is not installed.
        ServerProcessError: If the web server is already running in detached mode.
        BSMError: For other application-specific errors during startup.
    """
    mode = mode.lower()

    try:
        if mode not in ["direct", "detached"]:
            raise UserInputError("Invalid mode. Must be 'direct' or 'detached'.")

        logger.info(f"API: Attempting to start web server in '{mode}' mode...")
        manager = app_context.manager
        # --- Direct (Blocking) Mode ---
        if mode == "direct":
            manager.start_web_ui_direct(app_context, host, port, debug, threads)
            return {
                "status": "success",
                "message": "Web server (direct mode) shut down.",
            }

        # --- Detached (Background) Mode ---
        elif mode == "detached":
            if not PSUTIL_AVAILABLE:
                raise SystemError(
                    "Cannot start in detached mode: 'psutil' is required."
                )

            logger.info("API: Starting web server in detached mode...")
            pid_file_path = manager.get_web_ui_pid_path()
            expected_exe = manager.get_web_ui_executable_path()
            expected_arg = manager.get_web_ui_expected_start_arg()

            # Check for an existing, valid PID file.
            existing_pid = None
            try:
                existing_pid = system_process_utils.read_pid_from_file(pid_file_path)
            except FileOperationError:  # Corrupt PID file.
                system_process_utils.remove_pid_file_if_exists(pid_file_path)

            # If a PID exists, verify the process is still running and correct.
            if existing_pid and system_process_utils.is_process_running(existing_pid):
                try:
                    system_process_utils.verify_process_identity(
                        existing_pid, expected_exe, expected_arg
                    )
                    # If verification passes, the server is already running.
                    raise ServerProcessError(
                        f"Web server already running (PID: {existing_pid})."
                    )
                except ServerProcessError:
                    # The PID points to the wrong process. Clean up the stale file.
                    system_process_utils.remove_pid_file_if_exists(pid_file_path)
            else:
                # The PID is stale or doesn't exist. Clean up the file.
                system_process_utils.remove_pid_file_if_exists(pid_file_path)

            # Construct the command to launch the new detached process.
            command = [str(expected_exe), "web", "start", "--mode", "direct"]
            hosts_to_add = []
            if host:
                hosts_to_add.append(host)

            if debug:
                command.append("--debug")

            # Launch the process and write the new PID to the file.
            new_pid = system_process_utils.launch_detached_process(
                command, pid_file_path
            )
            return {
                "status": "success",
                "pid": new_pid,
                "message": f"Web server started (PID: {new_pid}).",
            }

    except BSMError as e:
        logger.error(f"API: Handled error starting web server: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}
    except Exception as e:
        logger.error(f"API: Unexpected error starting web server: {e}", exc_info=True)
        return {"status": "error", "message": f"Unexpected error: {str(e)}"}

    return {}


@trigger_plugin_event(before="before_web_server_stop", after="after_web_server_stop")
def stop_web_server_api(app_context: AppContext) -> Dict[str, str]:
    """Stops the detached web server process.

    This function reads the PID from the web server's PID file (path obtained
    via :meth:`~bedrock_server_manager.core.manager.BedrockServerManager.get_web_ui_pid_path`),
    verifies that the process is the correct one using expected executable and arguments
    (from :class:`~bedrock_server_manager.core.manager.BedrockServerManager`),
    and then terminates it. Uses utilities from
    :mod:`~bedrock_server_manager.core.system.process`.
    Requires the `psutil` library.
    Triggers ``before_web_server_stop`` and ``after_web_server_stop`` plugin events.

    Returns:
        Dict[str, str]: A dictionary with the operation result.
        If successfully stopped: ``{"status": "success", "message": "Web server (PID: <pid>) stopped."}``
        If not running (no PID file or stale PID): ``{"status": "success", "message": "Web server not running..."}``
        On error (e.g., PID file error, process mismatch, termination error):
        ``{"status": "error", "message": "<error_message>"}``.

    Raises:
        SystemError: If `psutil` is not installed.
        BSMError: Propagates errors from underlying operations, including:
            :class:`~.error.FileOperationError` (PID file issues),
            :class:`~.error.ServerProcessError` (process verification failure),
            :class:`~.error.ServerStopError` (termination failure),
            :class:`~.error.ConfigurationError` (if web UI paths not configured in BSM).
    """
    try:
        logger.info("API: Attempting to stop detached web server...")
        if not PSUTIL_AVAILABLE:
            raise SystemError("'psutil' not installed. Cannot manage processes.")

        manager = app_context.manager
        pid_file_path = manager.get_web_ui_pid_path()
        expected_exe = manager.get_web_ui_executable_path()
        expected_arg = manager.get_web_ui_expected_start_arg()

        # Read the PID from the file.
        pid = system_process_utils.read_pid_from_file(pid_file_path)
        if pid is None:
            system_process_utils.remove_pid_file_if_exists(pid_file_path)
            return {
                "status": "success",
                "message": "Web server not running (no valid PID file).",
            }

        # Check if the process is actually running.
        if not system_process_utils.is_process_running(pid):
            system_process_utils.remove_pid_file_if_exists(pid_file_path)
            return {
                "status": "success",
                "message": f"Web server not running (stale PID {pid}).",
            }

        # Verify it's the correct process before terminating.
        system_process_utils.verify_process_identity(pid, expected_exe)
        system_process_utils.terminate_process_by_pid(pid)
        system_process_utils.remove_pid_file_if_exists(pid_file_path)
        return {"status": "success", "message": f"Web server (PID: {pid}) stopped."}

    except (FileOperationError, ServerProcessError) as e:
        # Clean up the PID file if there's a file error or process mismatch.
        manager = app_context.manager
        system_process_utils.remove_pid_file_if_exists(manager.get_web_ui_pid_path())
        error_type = (
            "PID file error"
            if isinstance(e, FileOperationError)
            else "Process verification failed"
        )
        return {"status": "error", "message": f"{error_type}: {e}. PID file removed."}
    except BSMError as e:
        return {"status": "error", "message": f"Error stopping web server: {e}"}
    except Exception as e:
        logger.error(f"API: Unexpected error stopping web server: {e}", exc_info=True)
        return {"status": "error", "message": f"Unexpected error: {str(e)}"}


@plugin_method("get_web_server_status")
def get_web_server_status_api(app_context: AppContext) -> Dict[str, Any]:
    """Checks the status of the web server process.

    This function verifies the web server's status by checking for a valid
    PID file (path obtained via
    :meth:`~bedrock_server_manager.core.manager.BedrockServerManager.get_web_ui_pid_path`)
    and then inspecting the process itself (using utilities from
    :mod:`~bedrock_server_manager.core.system.process`) to ensure it is running
    and is the correct executable (details from
    :class:`~bedrock_server_manager.core.manager.BedrockServerManager`).
    Requires the `psutil` library.

    Returns:
        Dict[str, Any]: A dictionary with the web server's status.
        The ``"status"`` field can be one of "RUNNING", "STOPPED",
        "MISMATCHED_PROCESS", or "ERROR".
        If running, ``"pid"`` (int) will be present.
        A ``"message"`` (str) field provides details.
        Example: ``{"status": "RUNNING", "pid": 1234, "message": "Web server running..."}``

    Raises:
        BSMError: Can be raised by underlying operations if critical errors occur
            (e.g., :class:`~.error.ConfigurationError` if web UI paths are not set up
            in BedrockServerManager), though many operational errors are returned
            in the status dictionary.
    """
    logger.debug("API: Getting web server status...")
    if not PSUTIL_AVAILABLE:
        return {
            "status": "ERROR",
            "message": "'psutil' not installed. Cannot get process status.",
        }
    pid = None
    try:
        manager = app_context.manager
        pid_file_path = manager.get_web_ui_pid_path()
        expected_exe = manager.get_web_ui_executable_path()
        expected_arg = manager.get_web_ui_expected_start_arg()

        try:
            pid = system_process_utils.read_pid_from_file(pid_file_path)
        except FileOperationError:  # Handle corrupt PID file.
            system_process_utils.remove_pid_file_if_exists(pid_file_path)
            return {
                "status": "STOPPED",
                "pid": None,
                "message": "Corrupt PID file removed.",
            }

        # Case: No PID file, or PID file was empty.
        if pid is None:
            if os.path.exists(pid_file_path):  # Clean up empty file.
                system_process_utils.remove_pid_file_if_exists(pid_file_path)
            return {
                "status": "STOPPED",
                "pid": None,
                "message": "Web server not running (no PID file).",
            }

        # Case: PID file exists, but process is not running.
        if not system_process_utils.is_process_running(pid):
            system_process_utils.remove_pid_file_if_exists(pid_file_path)
            return {
                "status": "STOPPED",
                "pid": pid,
                "message": f"Stale PID {pid}, process not running.",
            }

        # Case: Process is running, verify it's the correct one.
        try:
            system_process_utils.verify_process_identity(
                pid, expected_exe, expected_arg
            )
            return {
                "status": "RUNNING",
                "pid": pid,
                "message": f"Web server running with PID {pid}.",
            }
        except ServerProcessError as e:
            # Case: PID points to a different, unrelated process.
            return {"status": "MISMATCHED_PROCESS", "pid": pid, "message": str(e)}

    except BSMError as e:  # Catches ConfigurationError, SystemError, etc.
        return {
            "status": "ERROR",
            "pid": pid,
            "message": f"An application error occurred: {e}",
        }
    except Exception as e:
        logger.error(
            f"API: Unexpected error getting web server status: {e}", exc_info=True
        )
        return {
            "status": "ERROR",
            "pid": None,
            "message": f"Unexpected error: {str(e)}",
        }


@trigger_plugin_event(
    before="before_web_service_change", after="after_web_service_change"
)
def create_web_ui_service(
    app_context: AppContext,
    autostart: bool = False,
    system: bool = False,
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> Dict[str, str]:
    """Creates (or updates) a system service for the Web UI.

    On Linux, this creates a systemd user service. On Windows, this creates a
    Windows Service (typically requires Administrator privileges).
    This function calls
    :meth:`~bedrock_server_manager.core.manager.BedrockServerManager.create_web_service_file`,
    and then either
    :meth:`~bedrock_server_manager.core.manager.BedrockServerManager.enable_web_service` or
    :meth:`~bedrock_server_manager.core.manager.BedrockServerManager.disable_web_service`
    based on the `autostart` flag.
    Triggers ``before_web_service_change`` and ``after_web_service_change`` plugin events.

    Args:
        autostart (bool, optional): If ``True``, the service will be enabled
            to start automatically on system boot/login. If ``False``, it will be
            created but left disabled. Defaults to ``False``.
        system (bool, optional): If ``True``, creates a system-wide service on
            Linux. This option is ignored on other operating systems. Defaults to ``False``.
        username (Optional[str], optional): The username to run the service as on
            Windows. This option is ignored on other operating systems. Defaults to ``None``.
        password (Optional[str], optional): The password for the user on Windows.
            This option is ignored on other operating systems. Defaults to ``None``.

    Returns:
        Dict[str, str]: A dictionary with the operation result.
        On success: ``{"status": "success", "message": "Web UI system service created and <enabled/disabled> successfully."}``
        On error: ``{"status": "error", "message": "<error_message>"}``.

    Raises:
        BSMError: Propagates errors from the underlying service management calls,
            such as :class:`~.error.SystemError`, :class:`~.error.PermissionsError`,
            :class:`~.error.CommandNotFoundError`, or :class:`~.error.FileOperationError`.
    """
    try:
        manager = app_context.manager
        if not manager.can_manage_services:
            return {
                "status": "error",
                "message": "System service management tool (systemctl/sc.exe) not found. Cannot manage Web UI service.",
            }

        manager.create_web_service_file(
            system=system, username=username, password=password
        )

        if autostart:
            manager.enable_web_service(system=system)
            action_done = "created and enabled"
        else:
            manager.disable_web_service()
            action_done = "created and disabled"

        return {
            "status": "success",
            "message": f"Web UI system service {action_done} successfully.",
        }

    except BSMError as e:
        logger.error(f"API: Failed to create Web UI system service: {e}", exc_info=True)
        return {"status": "error", "message": f"Failed to create Web UI service: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error creating Web UI system service: {e}", exc_info=True
        )
        return {
            "status": "error",
            "message": f"Unexpected error creating Web UI service: {e}",
        }


@trigger_plugin_event(
    before="before_web_service_change", after="after_web_service_change"
)
def enable_web_ui_service(
    app_context: AppContext, system: bool = False
) -> Dict[str, str]:
    """Enables the Web UI system service for autostart.

    On Linux, this enables the systemd user service. On Windows, this sets the
    Windows Service start type to 'Automatic' (typically requires Administrator
    privileges). It calls
    :meth:`~bedrock_server_manager.core.manager.BedrockServerManager.enable_web_service`.
    Triggers ``before_web_service_change`` and ``after_web_service_change`` plugin events.

    Args:
        system (bool, optional): If ``True``, enables a system-wide service on
            Linux. This option is ignored on other operating systems. Defaults to ``False``.

    Returns:
        Dict[str, str]: A dictionary with the operation result.
        On success: ``{"status": "success", "message": "Web UI service enabled successfully."}``
        If service management tools are unavailable:
        ``{"status": "error", "message": "System service management tool ... not found."}``
        On other error: ``{"status": "error", "message": "<error_message>"}``.

    Raises:
        BSMError: Propagates errors from the underlying
            :meth:`~bedrock_server_manager.core.manager.BedrockServerManager.enable_web_service`
            call (e.g., :class:`~.error.SystemError`, :class:`~.error.PermissionsError`).
    """
    try:
        manager = app_context.manager
        if not manager.can_manage_services:
            return {
                "status": "error",
                "message": "System service management tool (systemctl/sc.exe) not found. Cannot manage Web UI service.",
            }
        manager.enable_web_service(system=system)
        return {
            "status": "success",
            "message": "Web UI service enabled successfully.",
        }
    except BSMError as e:
        logger.error(f"API: Failed to enable Web UI system service: {e}", exc_info=True)
        return {"status": "error", "message": f"Failed to enable Web UI service: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error enabling Web UI system service: {e}", exc_info=True
        )
        return {
            "status": "error",
            "message": f"Unexpected error enabling Web UI service: {e}",
        }


@trigger_plugin_event(
    before="before_web_service_change", after="after_web_service_change"
)
def disable_web_ui_service(
    app_context: AppContext, system: bool = False
) -> Dict[str, str]:
    """Disables the Web UI system service from autostarting.

    On Linux, this disables the systemd user service. On Windows, this sets the
    Windows Service start type to 'Disabled' or 'Manual' (typically requires
    Administrator privileges). It calls
    :meth:`~bedrock_server_manager.core.manager.BedrockServerManager.disable_web_service`.
    Triggers ``before_web_service_change`` and ``after_web_service_change`` plugin events.

    Args:
        system (bool, optional): If ``True``, disables a system-wide service on
            Linux. This option is ignored on other operating systems. Defaults to ``False``.

    Returns:
        Dict[str, str]: A dictionary with the operation result.
        On success: ``{"status": "success", "message": "Web UI service disabled successfully."}``
        If service management tools are unavailable:
        ``{"status": "error", "message": "System service management tool ... not found."}``
        On other error: ``{"status": "error", "message": "<error_message>"}``.

    Raises:
        BSMError: Propagates errors from the underlying
            :meth:`~bedrock_server_manager.core.manager.BedrockServerManager.disable_web_service`
            call (e.g., :class:`~.error.SystemError`, :class:`~.error.PermissionsError`).
    """
    try:
        manager = app_context.manager
        if not manager.can_manage_services:
            return {
                "status": "error",
                "message": "System service management tool (systemctl/sc.exe) not found. Cannot manage Web UI service.",
            }
        manager.disable_web_service(system=system)
        return {
            "status": "success",
            "message": "Web UI service disabled successfully.",
        }
    except BSMError as e:
        logger.error(
            f"API: Failed to disable Web UI system service: {e}", exc_info=True
        )
        return {
            "status": "error",
            "message": f"Failed to disable Web UI service: {e}",
        }
    except Exception as e:
        logger.error(
            f"API: Unexpected error disabling Web UI system service: {e}", exc_info=True
        )
        return {
            "status": "error",
            "message": f"Unexpected error disabling Web UI service: {e}",
        }


@trigger_plugin_event(
    before="before_web_service_change", after="after_web_service_change"
)
def remove_web_ui_service(
    app_context: AppContext, system: bool = False
) -> Dict[str, str]:
    """Removes the Web UI system service.

    The service should ideally be stopped and disabled before removal.
    This function calls
    :meth:`~bedrock_server_manager.core.manager.BedrockServerManager.remove_web_service_file`.

    .. warning::
        This is a **DESTRUCTIVE** operation that removes the service definition
        from the system.

    Triggers ``before_web_service_change`` and ``after_web_service_change`` plugin events.

    Args:
        system (bool, optional): If ``True``, removes a system-wide service on
            Linux. This option is ignored on other operating systems. Defaults to ``False``.

    Returns:
        Dict[str, str]: A dictionary with the operation result.
        On success (service removed or was not found):
        ``{"status": "success", "message": "Web UI service removed successfully."}``
        If service management tools are unavailable:
        ``{"status": "error", "message": "System service management tool ... not found."}``
        On other error: ``{"status": "error", "message": "<error_message>"}``.

    Raises:
        BSMError: Propagates errors from the underlying
            :meth:`~bedrock_server_manager.core.manager.BedrockServerManager.remove_web_service_file`
            call (e.g., :class:`~.error.SystemError`, :class:`~.error.PermissionsError`,
            :class:`~.error.FileOperationError`).
    """
    try:
        manager = app_context.manager
        if not manager.can_manage_services:
            return {
                "status": "error",
                "message": "System service management tool (systemctl/sc.exe) not found. Cannot manage Web UI service.",
            }

        removed = manager.remove_web_service_file(system=system)
        if removed:
            return {
                "status": "success",
                "message": "Web UI service removed successfully.",
            }
        else:

            return {
                "status": "error",
                "message": "Web UI service removal failed or file not found.",
            }

    except BSMError as e:
        logger.error(f"API: Failed to remove Web UI system service: {e}", exc_info=True)
        return {"status": "error", "message": f"Failed to remove Web UI service: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error removing Web UI system service: {e}", exc_info=True
        )
        return {
            "status": "error",
            "message": f"Unexpected error removing Web UI service: {e}",
        }


def get_web_ui_service_status(
    app_context: AppContext, system: bool = False
) -> Dict[str, Any]:
    """Gets the current status of the Web UI system service.

    This function calls several methods on the
    :class:`~bedrock_server_manager.core.manager.BedrockServerManager` instance:
    :meth:`~.check_web_service_exists`,
    :meth:`~.is_web_service_active`, and
    :meth:`~.is_web_service_enabled`.

    Args:
        system (bool, optional): If ``True``, checks a system-wide service on
            Linux. This option is ignored on other operating systems. Defaults to ``False``.

    Returns:
        Dict[str, Any]: A dictionary with the operation result.
        On success: ``{"status": "success", "service_exists": bool, "is_active": bool, "is_enabled": bool, "message": Optional[str]}``.
        - ``service_exists``: ``True`` if the service definition is found on the system.
        - ``is_active``: ``True`` if the service is currently running.
        - ``is_enabled``: ``True`` if the service is set to start automatically.
        A "message" field may be present if service management tools are unavailable.
        On error during checks: ``{"status": "error", "message": "<error_message>"}``.
    """
    response_data: Dict[str, Any] = {
        "service_exists": False,
        "is_active": False,
        "is_enabled": False,
    }
    try:
        manager = app_context.manager
        if not manager.can_manage_services:
            return {
                "status": "success",
                "message": "System service management tool (systemctl/sc.exe) not found. Cannot determine Web UI service status.",
                **response_data,
            }

        response_data["service_exists"] = manager.check_web_service_exists(
            system=system
        )
        if response_data["service_exists"]:
            response_data["is_active"] = manager.is_web_service_active(system=system)
            response_data["is_enabled"] = manager.is_web_service_enabled(system=system)

        return {"status": "success", **response_data}

    except BSMError as e:
        logger.error(f"API: Error getting Web UI service status: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"Error getting Web UI service status: {e}",
        }
    except Exception as e:
        logger.error(
            f"API: Unexpected error getting Web UI service status: {e}", exc_info=True
        )
        return {
            "status": "error",
            "message": f"Unexpected error getting Web UI service status: {e}",
        }
