# bedrock_server_manager/api/system.py
"""Provides API functions for system-level server interactions and information.

This module serves as an interface for querying system-related information about
server processes and for managing their integration with the host operating system's
service management capabilities. It primarily orchestrates calls to the
:class:`~bedrock_server_manager.core.bedrock_server.BedrockServer` class.

Key functionalities include:
    - Querying server process resource usage (e.g., PID, CPU, memory) via
      :func:`~.get_bedrock_process_info`.
    - Managing OS-level services (systemd on Linux, Windows Services on Windows)
      for servers, including creation (:func:`~.create_server_service`),
      enabling (:func:`~.enable_server_service`), and disabling
      (:func:`~.disable_server_service`) auto-start.
    - Configuring server-specific settings like autoupdate behavior via
      :func:`~.set_autoupdate`.

These functions are designed for use by higher-level application components,
such as the web UI or CLI, to provide system-level control and monitoring.
"""

import logging
import time

from ..context import AppContext
from ..error import (
    BSMError,
    InvalidServerNameError,
)
from ..logging import log_operation_error
from ..plugins.api_bridge import api_method
from ..state_revision import revision_clock
from .models.health import (
    GetApplicationHealthRequest,
    GetApplicationHealthResponse,
    HealthCheck,
)
from .models.metrics import GetApplicationMetricsRequest, GetApplicationMetricsResponse
from .models.system import (
    GetBedrockProcessInfoRequest,
    GetBedrockProcessInfoResponse,
    GetServerRunningStatusRequest,
    GetServerRunningStatusResponse,
)

logger = logging.getLogger(__name__)


@api_method("get_server_running_status")
async def get_server_running_status(
    request: GetServerRunningStatusRequest, *, app_context: AppContext
) -> GetServerRunningStatusResponse:
    """Checks if the server process is currently running.

    Accepts GetServerRunningStatusRequest and returns GetServerRunningStatusResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    server_name = request.server_name
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    logger.debug("Checking running status for server '%s'...", server_name)
    try:
        server = app_context.get_server(server_name)
        revision = revision_clock.capture()
        is_running = await server.is_running()
        logger.debug(
            "is_running() check for '%s' returned: %s", server_name, is_running
        )
        return GetServerRunningStatusResponse.model_validate(
            {"status": "success", "is_running": is_running, **revision}
        )
    except BSMError as e:
        log_operation_error(
            logger,
            "Error checking running status for '%s': %s",
            server_name,
            e,
            error=e,
        )
        raise
    except Exception as e:
        log_operation_error(
            logger,
            "Unexpected error checking running status for '%s': %s",
            server_name,
            e,
            error=e,
        )
        raise


@api_method("get_bedrock_process_info")
async def get_bedrock_process_info(
    request: GetBedrockProcessInfoRequest, *, app_context: AppContext
) -> GetBedrockProcessInfoResponse:
    """Retrieves resource usage for a running Bedrock server process.

    Accepts GetBedrockProcessInfoRequest and returns GetBedrockProcessInfoResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    server_name = request.server_name
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    logger.debug("Getting process info for server '%s'...", server_name)
    try:
        server = app_context.get_server(server_name)
        revision = revision_clock.capture()
        process_info = await server.get_process_info()
        if process_info is None:
            return GetBedrockProcessInfoResponse.model_validate(
                {
                    "status": "success",
                    "message": f"Server process '{server_name}' not found or is inaccessible.",
                    "process_info": None,
                    **revision,
                }
            )
        else:
            return GetBedrockProcessInfoResponse.model_validate(
                {"status": "success", "process_info": process_info, **revision}
            )
    except BSMError as e:
        log_operation_error(
            logger, "Failed to get process info for '%s': %s", server_name, e, error=e
        )
        raise
    except Exception as e:
        log_operation_error(
            logger,
            "Unexpected error getting process info for '%s': %s",
            server_name,
            e,
            error=e,
        )
        raise


@api_method("get_application_metrics")
async def get_application_metrics(
    request: GetApplicationMetricsRequest, *, app_context: AppContext
) -> GetApplicationMetricsResponse:
    """Return shared, bounded performance history without sampling per request."""
    return await app_context.metrics_service.snapshot()


@api_method("get_application_health")
async def get_application_health(
    request: GetApplicationHealthRequest, *, app_context: AppContext
) -> GetApplicationHealthResponse:
    """Read-only readiness checks; dependency errors never expose credentials."""
    try:
        database_healthy = await app_context.db.check_health()
    except Exception:
        database_healthy = False
    results = {
        "lifecycle": (
            app_context.lifecycle_phase == "ready",
            "Application ready",
            f"Application {app_context.lifecycle_phase}",
        ),
        "database": (database_healthy, "Database reachable", "Database unavailable"),
        "state": (
            app_context.state_loaded,
            "Application state loaded",
            "Application state unavailable",
        ),
        "metrics": (
            app_context.metrics_service.check_health(),
            "Metrics sampler active",
            "Metrics sampler stopped or stale",
        ),
    }
    checks = {
        name: HealthCheck(healthy=healthy, message=ok if healthy else failed)
        for name, (healthy, ok, failed) in results.items()
    }
    return GetApplicationHealthResponse(
        lifecycle=app_context.lifecycle_phase,
        health=(
            "healthy" if all(check.healthy for check in checks.values()) else "degraded"
        ),
        checks=checks,
        checked_at=time.time(),
    )
