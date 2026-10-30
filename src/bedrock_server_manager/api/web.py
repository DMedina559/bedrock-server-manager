"""Typed API operations for web system-service configuration.

Hosting process control belongs to bedrock_server_manager.web, not AppAPI.
"""

import logging
from typing import Any, Dict

from ..context import AppContext
from ..core import service
from ..core.system.base import can_manage_services
from ..error import BSMError, DependencyUnavailableError
from ..logging import log_operation_error
from .contract import validate_contract
from .models.web import (
    CreateWebUiServiceRequest,
    CreateWebUiServiceResponse,
    DisableWebUiServiceRequest,
    DisableWebUiServiceResponse,
    EnableWebUiServiceRequest,
    EnableWebUiServiceResponse,
    GetWebUiServiceStatusRequest,
    GetWebUiServiceStatusResponse,
    RemoveWebUiServiceRequest,
    RemoveWebUiServiceResponse,
)

logger = logging.getLogger(__name__)


@validate_contract
def create_web_ui_service(
    request: CreateWebUiServiceRequest, *, app_context: AppContext
) -> CreateWebUiServiceResponse:
    """Create (or updates) a system service for the Web UI."""
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
            config_dir=app_context.config_dir,
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
        return CreateWebUiServiceResponse(
            status="success",
            message=f"Web UI system service {action_done} successfully.",
        )
    except BSMError as e:
        log_operation_error(
            logger, "Failed to create Web UI system service: %s", e, error=e
        )
        raise
    except Exception as e:
        log_operation_error(
            logger, "Unexpected error creating Web UI system service: %s", e, error=e
        )
        raise


@validate_contract
def enable_web_ui_service(
    request: EnableWebUiServiceRequest, *, app_context: AppContext
) -> EnableWebUiServiceResponse:
    """Enables the Web UI system service for autostart."""
    system = request.system
    try:
        if not can_manage_services():
            raise BSMError(
                "System service management tool (systemctl/sc.exe) not found. Cannot manage Web UI service."
            )
        service.enable_web_service(system=system)
        return EnableWebUiServiceResponse(
            status="success", message="Web UI service enabled successfully."
        )
    except BSMError as e:
        log_operation_error(
            logger, "Failed to enable Web UI system service: %s", e, error=e
        )
        raise
    except Exception as e:
        log_operation_error(
            logger, "Unexpected error enabling Web UI system service: %s", e, error=e
        )
        raise


@validate_contract
def disable_web_ui_service(
    request: DisableWebUiServiceRequest, *, app_context: AppContext
) -> DisableWebUiServiceResponse:
    """Disables the Web UI system service from autostarting."""
    system = request.system
    try:
        if not can_manage_services():
            raise BSMError(
                "System service management tool (systemctl/sc.exe) not found. Cannot manage Web UI service."
            )
        service.disable_web_service(system=system)
        return DisableWebUiServiceResponse(
            status="success", message="Web UI service disabled successfully."
        )
    except BSMError as e:
        log_operation_error(
            logger, "Failed to disable Web UI system service: %s", e, error=e
        )
        raise
    except Exception as e:
        log_operation_error(
            logger, "Unexpected error disabling Web UI system service: %s", e, error=e
        )
        raise


@validate_contract
def remove_web_ui_service(
    request: RemoveWebUiServiceRequest, *, app_context: AppContext
) -> RemoveWebUiServiceResponse:
    """Remove the Web UI system service."""
    system = request.system
    try:
        if not can_manage_services():
            raise BSMError(
                "System service management tool (systemctl/sc.exe) not found. Cannot manage Web UI service."
            )
        removed = service.remove_web_service_file(system=system)
        if removed:
            return RemoveWebUiServiceResponse(
                status="success", message="Web UI service removed successfully."
            )
        else:
            raise BSMError("Web UI service removal failed or file not found.")
    except BSMError as e:
        log_operation_error(
            logger, "Failed to remove Web UI system service: %s", e, error=e
        )
        raise
    except Exception as e:
        log_operation_error(
            logger, "Unexpected error removing Web UI system service: %s", e, error=e
        )
        raise


@validate_contract
def get_web_ui_service_status(
    request: GetWebUiServiceStatusRequest, *, app_context: AppContext
) -> GetWebUiServiceStatusResponse:
    """Return the current status of the Web UI system service."""
    system = request.system
    response_data: Dict[str, Any] = {
        "service_exists": False,
        "is_active": False,
        "is_enabled": False,
    }
    try:
        if not can_manage_services():
            raise DependencyUnavailableError(
                "System service management is unavailable."
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
        log_operation_error(
            logger, "Error getting Web UI service status: %s", e, error=e
        )
        raise
    except Exception as e:
        log_operation_error(
            logger, "Unexpected error getting Web UI service status: %s", e, error=e
        )
        raise
