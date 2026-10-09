# bedrock_server_manager/api/web.py
"""Provides API functions for managing the application's own web user interface.

This module contains the logic for controlling the lifecycle and querying the
status of the built-in web UI, which is powered by FastAPI. It handles:

    - Starting the web server in 'direct' (blocking) or 'detached' (background) modes
      (:func:`~.start_web_server`).
    - Stopping the detached web server process (:func:`~.stop_web_server`).
    - Checking the runtime status of the web server (:func:`~.get_web_server_status`).
    - Managing the system service for the Web UI (create, enable, disable, remove, get status)
      via functions like :func:`~.create_web_ui_service` and :func:`~.get_web_ui_service_status`.

These functions are intended for programmatic control of the application's web server,
often used by CLI commands or service management scripts.
"""

import asyncio
import logging
import os
from typing import Any, Dict

from ..context import AppContext
from ..core import service
from ..core.system import process as system_process_utils
from ..core.system.base import can_manage_services
from ..error import (
    BSMError,
    FileOperationError,
    ServerProcessError,
    SystemError,
    UserInputError,
)
from ..plugins.api_contract import validate_contract
from .models.web import (
    CreateWebUiServiceRequest,
    CreateWebUiServiceResponse,
    DisableWebUiServiceRequest,
    DisableWebUiServiceResponse,
    EnableWebUiServiceRequest,
    EnableWebUiServiceResponse,
    GetWebServerStatusRequest,
    GetWebServerStatusResponse,
    GetWebUiServiceStatusRequest,
    GetWebUiServiceStatusResponse,
    RemoveWebUiServiceRequest,
    RemoveWebUiServiceResponse,
    StartWebServerRequest,
    StartWebServerResponse,
    StopWebServerRequest,
    StopWebServerResponse,
)

try:
    import psutil  # noqa: F401

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


logger = logging.getLogger(__name__)


@validate_contract
def start_web_server(
    request: StartWebServerRequest, *, app_context: AppContext
) -> StartWebServerResponse:
    """Starts the application's web server.

    Accepts StartWebServerRequest and returns StartWebServerResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    host = request.host
    port = request.port
    debug = request.debug
    mode = request.mode
    try:
        if mode not in ["direct", "detached"]:
            raise UserInputError("Invalid mode. Must be 'direct' or 'detached'.")
        logger.info(f"API: Attempting to start web server in '{mode}' mode...")
        if mode == "direct":
            logger.info("BSM: Starting web application in direct mode (blocking)...")
            try:
                from ..web.main import run_web_server as run_bsm_web_application

                run_bsm_web_application(
                    app_context=app_context, host=host, port=port, debug=debug
                )
                logger.info("BSM: Web application (direct mode) shut down.")
            except (RuntimeError, ImportError) as e:
                logger.critical(
                    f"BSM: Failed to start web application directly: {e}", exc_info=True
                )
                raise
            return StartWebServerResponse.model_validate(
                {"status": "success", "message": "Web server (direct mode) shut down."}
            )
        elif mode == "detached":
            if not PSUTIL_AVAILABLE:
                raise SystemError(
                    "Cannot start in detached mode: 'psutil' is required."
                )
            logger.info("API: Starting web server in detached mode...")
            import sys

            pid_file_path = os.path.join(
                app_context.settings.config_dir, "web_server.pid"
            )
            existing_pid = None
            try:
                existing_pid = asyncio.run(
                    system_process_utils.read_pid_from_file(pid_file_path)
                )
            except FileOperationError:
                asyncio.run(
                    system_process_utils.remove_pid_file_if_exists(pid_file_path)
                )
            if existing_pid and asyncio.run(
                system_process_utils.is_process_running(existing_pid)
            ):
                try:
                    asyncio.run(
                        system_process_utils.verify_process_identity(
                            pid=existing_pid, expected_command_args=["web", "start"]
                        )
                    )
                    raise ServerProcessError(
                        f"Web server already running (PID: {existing_pid})."
                    )
                except ServerProcessError:
                    asyncio.run(
                        system_process_utils.remove_pid_file_if_exists(pid_file_path)
                    )
            else:
                asyncio.run(
                    system_process_utils.remove_pid_file_if_exists(pid_file_path)
                )
            command = [
                sys.executable,
                "-m",
                "bedrock_server_manager",
                "web",
                "start",
                "--mode",
                "direct",
            ]
            hosts_to_add = []
            if host:
                hosts_to_add.append(host)
            if debug:
                command.append("--debug")
            new_pid = asyncio.run(
                system_process_utils.launch_detached_process(command, pid_file_path)
            )
            return StartWebServerResponse.model_validate(
                {
                    "status": "success",
                    "pid": new_pid,
                    "message": f"Web server started (PID: {new_pid}).",
                }
            )
    except BSMError as e:
        logger.error(f"API: Handled error starting web server: {e}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"API: Unexpected error starting web server: {e}", exc_info=True)
        raise
    raise RuntimeError("Unsupported web server mode")


@validate_contract
def stop_web_server(
    request: StopWebServerRequest, *, app_context: AppContext
) -> StopWebServerResponse:
    """Stops the detached web server process.

    Accepts StopWebServerRequest and returns StopWebServerResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    try:
        logger.info("API: Attempting to stop detached web server...")
        if not PSUTIL_AVAILABLE:
            raise SystemError("'psutil' not installed. Cannot manage processes.")
        pid_file_path = os.path.join(app_context.settings.config_dir, "web_server.pid")
        pid = asyncio.run(system_process_utils.read_pid_from_file(pid_file_path))
        if pid is None:
            asyncio.run(system_process_utils.remove_pid_file_if_exists(pid_file_path))
            return StopWebServerResponse.model_validate(
                {
                    "status": "success",
                    "message": "Web server not running (no valid PID file).",
                }
            )
        if not asyncio.run(system_process_utils.is_process_running(pid)):
            asyncio.run(system_process_utils.remove_pid_file_if_exists(pid_file_path))
            return StopWebServerResponse.model_validate(
                {
                    "status": "success",
                    "message": f"Web server not running (stale PID {pid}).",
                }
            )
        asyncio.run(
            system_process_utils.verify_process_identity(
                pid=pid, expected_command_args=["web", "start"]
            )
        )
        asyncio.run(system_process_utils.terminate_process_by_pid(pid))
        asyncio.run(system_process_utils.remove_pid_file_if_exists(pid_file_path))
        return StopWebServerResponse.model_validate(
            {"status": "success", "message": f"Web server (PID: {pid}) stopped."}
        )
    except (FileOperationError, ServerProcessError) as e:
        asyncio.run(
            system_process_utils.remove_pid_file_if_exists(
                os.path.join(app_context.settings.config_dir, "web_server.pid")
            )
        )
        (
            "PID file error"
            if isinstance(e, FileOperationError)
            else "Process verification failed"
        )
        raise
    except BSMError:
        raise
    except Exception as e:
        logger.error(f"API: Unexpected error stopping web server: {e}", exc_info=True)
        raise


@validate_contract
def get_web_server_status(
    request: GetWebServerStatusRequest, *, app_context: AppContext
) -> GetWebServerStatusResponse:
    """Checks the status of the web server process.

    Accepts GetWebServerStatusRequest and returns GetWebServerStatusResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    logger.debug("API: Getting web server status...")
    if not PSUTIL_AVAILABLE:
        raise BSMError("'psutil' not installed. Cannot get process status.")
    pid = None
    try:
        pid_file_path = os.path.join(app_context.settings.config_dir, "web_server.pid")
        expected_arg = ["web", "start"]
        try:
            pid = asyncio.run(system_process_utils.read_pid_from_file(pid_file_path))
        except FileOperationError:
            asyncio.run(system_process_utils.remove_pid_file_if_exists(pid_file_path))
            return GetWebServerStatusResponse.model_validate(
                {
                    "status": "STOPPED",
                    "pid": None,
                    "message": "Corrupt PID file removed.",
                }
            )
        if pid is None:
            if os.path.exists(pid_file_path):
                asyncio.run(
                    system_process_utils.remove_pid_file_if_exists(pid_file_path)
                )
            return GetWebServerStatusResponse.model_validate(
                {
                    "status": "STOPPED",
                    "pid": None,
                    "message": "Web server not running (no PID file).",
                }
            )
        if not asyncio.run(system_process_utils.is_process_running(pid)):
            asyncio.run(system_process_utils.remove_pid_file_if_exists(pid_file_path))
            return GetWebServerStatusResponse.model_validate(
                {
                    "status": "STOPPED",
                    "pid": pid,
                    "message": f"Stale PID {pid}, process not running.",
                }
            )
        try:
            asyncio.run(
                system_process_utils.verify_process_identity(
                    pid=pid, expected_command_args=expected_arg
                )
            )
            return GetWebServerStatusResponse.model_validate(
                {
                    "status": "RUNNING",
                    "pid": pid,
                    "message": f"Web server running with PID {pid}.",
                }
            )
        except ServerProcessError as e:
            return GetWebServerStatusResponse.model_validate(
                {"status": "MISMATCHED_PROCESS", "pid": pid, "message": str(e)}
            )
    except BSMError:
        raise
    except Exception as e:
        logger.error(
            f"API: Unexpected error getting web server status: {e}", exc_info=True
        )
        raise


@validate_contract
def create_web_ui_service(
    request: CreateWebUiServiceRequest, *, app_context: AppContext
) -> CreateWebUiServiceResponse:
    """Creates (or updates) a system service for the Web UI.

    Accepts CreateWebUiServiceRequest and returns CreateWebUiServiceResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    autostart = request.autostart
    system = request.system
    username = request.username
    password = (
        request.password.get_secret_value() if request.password is not None else None
    )
    try:
        if not can_manage_services():
            raise BSMError(
                "System service management tool (systemctl/sc.exe) not found. Cannot manage Web UI service."
            )
        service.create_web_service_file(
            app_data_dir=app_context.data_dir,
            system=system,
            username=username,
            password=password,
        )
        if autostart:
            service.enable_web_service(system=system)
            action_done = "created and enabled"
        else:
            service.disable_web_service(system=system)
            action_done = "created and disabled"
        return CreateWebUiServiceResponse.model_validate(
            {
                "status": "success",
                "message": f"Web UI system service {action_done} successfully.",
            }
        )
    except BSMError as e:
        logger.error(f"API: Failed to create Web UI system service: {e}", exc_info=True)
        raise
    except Exception as e:
        logger.error(
            f"API: Unexpected error creating Web UI system service: {e}", exc_info=True
        )
        raise


@validate_contract
def enable_web_ui_service(
    request: EnableWebUiServiceRequest, *, app_context: AppContext
) -> EnableWebUiServiceResponse:
    """Enables the Web UI system service for autostart.

    Accepts EnableWebUiServiceRequest and returns EnableWebUiServiceResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    system = request.system
    try:
        if not can_manage_services():
            raise BSMError(
                "System service management tool (systemctl/sc.exe) not found. Cannot manage Web UI service."
            )
        service.enable_web_service(system=system)
        return EnableWebUiServiceResponse.model_validate(
            {"status": "success", "message": "Web UI service enabled successfully."}
        )
    except BSMError as e:
        logger.error(f"API: Failed to enable Web UI system service: {e}", exc_info=True)
        raise
    except Exception as e:
        logger.error(
            f"API: Unexpected error enabling Web UI system service: {e}", exc_info=True
        )
        raise


@validate_contract
def disable_web_ui_service(
    request: DisableWebUiServiceRequest, *, app_context: AppContext
) -> DisableWebUiServiceResponse:
    """Disables the Web UI system service from autostarting.

    Accepts DisableWebUiServiceRequest and returns DisableWebUiServiceResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    system = request.system
    try:
        if not can_manage_services():
            raise BSMError(
                "System service management tool (systemctl/sc.exe) not found. Cannot manage Web UI service."
            )
        service.disable_web_service(system=system)
        return DisableWebUiServiceResponse.model_validate(
            {"status": "success", "message": "Web UI service disabled successfully."}
        )
    except BSMError as e:
        logger.error(
            f"API: Failed to disable Web UI system service: {e}", exc_info=True
        )
        raise
    except Exception as e:
        logger.error(
            f"API: Unexpected error disabling Web UI system service: {e}", exc_info=True
        )
        raise


@validate_contract
def remove_web_ui_service(
    request: RemoveWebUiServiceRequest, *, app_context: AppContext
) -> RemoveWebUiServiceResponse:
    """Removes the Web UI system service.

    Accepts RemoveWebUiServiceRequest and returns RemoveWebUiServiceResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    system = request.system
    try:
        if not can_manage_services():
            raise BSMError(
                "System service management tool (systemctl/sc.exe) not found. Cannot manage Web UI service."
            )
        removed = service.remove_web_service_file(system=system)
        if removed:
            return RemoveWebUiServiceResponse.model_validate(
                {"status": "success", "message": "Web UI service removed successfully."}
            )
        else:
            raise BSMError("Web UI service removal failed or file not found.")
    except BSMError as e:
        logger.error(f"API: Failed to remove Web UI system service: {e}", exc_info=True)
        raise
    except Exception as e:
        logger.error(
            f"API: Unexpected error removing Web UI system service: {e}", exc_info=True
        )
        raise


@validate_contract
def get_web_ui_service_status(
    request: GetWebUiServiceStatusRequest, *, app_context: AppContext
) -> GetWebUiServiceStatusResponse:
    """Gets the current status of the Web UI system service.

    Accepts GetWebUiServiceStatusRequest and returns GetWebUiServiceStatusResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    system = request.system
    response_data: Dict[str, Any] = {
        "service_exists": False,
        "is_active": False,
        "is_enabled": False,
    }
    try:
        if not can_manage_services():
            return GetWebUiServiceStatusResponse.model_validate(
                {
                    "status": "success",
                    "message": "System service management tool (systemctl/sc.exe) not found. Cannot determine Web UI service status.",
                    **response_data,
                }
            )
        response_data["service_exists"] = service.check_web_service_exists(
            system=system
        )
        if response_data["service_exists"]:
            response_data["is_active"] = service.is_web_service_active(system=system)
            response_data["is_enabled"] = service.is_web_service_enabled(system=system)
        return GetWebUiServiceStatusResponse.model_validate(
            {"status": "success", **response_data}
        )
    except BSMError as e:
        logger.error(f"API: Error getting Web UI service status: {e}", exc_info=True)
        raise
    except Exception as e:
        logger.error(
            f"API: Unexpected error getting Web UI service status: {e}", exc_info=True
        )
        raise
