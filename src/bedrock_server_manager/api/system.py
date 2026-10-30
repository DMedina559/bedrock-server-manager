# bedrock_server_manager/api/system.py
"""Provide API functions for system-level server interactions and information."""

import logging
import os
import time

from ..config import get_installed_version
from ..context import AppContext
from ..error import (
    BSMError,
)
from ..logging import RepeatedFailureReporter, log_operation_error
from ..plugins.api_bridge import api_method
from ..state.revision import revision_clock
from .models.system import (
    GetApplicationHealthRequest,
    GetApplicationHealthResponse,
    GetApplicationMetricsRequest,
    GetApplicationMetricsResponse,
    GetBedrockProcessInfoRequest,
    GetBedrockProcessInfoResponse,
    GetServerRunningStatusRequest,
    GetServerRunningStatusResponse,
    HealthCheck,
)

logger = logging.getLogger(__name__)
_health_failures = RepeatedFailureReporter(logger)


@api_method("get_server_running_status")
async def get_server_running_status(
    request: GetServerRunningStatusRequest, *, app_context: AppContext
) -> GetServerRunningStatusResponse:
    """Check if the server process is currently running."""
    server_name = request.server_name
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
    """Return resource usage for a running Bedrock server process."""
    server_name = request.server_name
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
    result = await app_context.metrics_service.snapshot()
    return GetApplicationMetricsResponse.model_validate(result.model_dump())


@api_method("get_application_health")
async def get_application_health(
    request: GetApplicationHealthRequest, *, app_context: AppContext
) -> GetApplicationHealthResponse:
    """Read-only readiness checks; dependency errors never expose credentials."""
    try:
        database_healthy = await app_context.db.check_health()
        if database_healthy:
            _health_failures.recover("database")
    except Exception as error:
        _health_failures.report("database", "Health check %s failed: %s", error)
        database_healthy = False
    from ..utils.timezones import timezone_database_available

    results = {
        "timezone_data": (
            timezone_database_available(),
            "Regional timezone data available",
            "Regional timezone data unavailable; UTC schedules remain usable",
        ),
        "lifecycle": (
            app_context.is_ready,
            "Application ready",
            "Application runtime is not ready",
        ),
        "database": (database_healthy, "Database reachable", "Database unavailable"),
        "state": (
            app_context.state_loaded,
            "Application state loaded",
            "Application state unavailable",
        ),
        "scheduler": (
            app_context.scheduler.check_health(),
            "Scheduler loop active",
            "Scheduler loop stopped, failed, or stale",
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
        pid=os.getpid(),
        version=get_installed_version(),
        ready=app_context.is_ready,
        lifecycle=app_context.lifecycle_phase,
        health=(
            "healthy" if all(check.healthy for check in checks.values()) else "degraded"
        ),
        checks=checks,
        checked_at=time.time(),
    )
