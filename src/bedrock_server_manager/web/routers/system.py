"""FastAPI router for system info, themes, metrics, and health endpoints."""

import asyncio
import logging
import os

import aiofiles.ospath
from fastapi import APIRouter, Depends, HTTPException, Request, Security, status

from bedrock_server_manager.api.models import GetSystemAndAppInfoRequest

from ...api import system as system_api
from ...api.models.system import (
    GetApplicationHealthRequest,
    GetApplicationHealthResponse,
    GetApplicationMetricsRequest,
    GetApplicationMetricsResponse,
)
from ...context import AppContext
from ...services.lifecycle import LifecyclePhase
from ..access_metadata import describe_access
from ..access_policy import Permission
from ..deps import get_app_context
from ..deps.auth import require_permissions
from ..runtime import WebRuntime
from ..schemas import AppInfoResponse, ThemeListResponse, UserResponse
from .runtime import require_health_access

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/api/info",
    operation_id="get_system_info",
    tags=["Application"],
    response_model=AppInfoResponse,
)
@describe_access("public", authentication="none", additional_checks=[])
async def get_system_info(
    app_context: AppContext = Depends(get_app_context),
) -> AppInfoResponse:
    """Return general system and application information."""
    logger.debug("Request for system and app info.")
    from ...api.application import get_system_and_app_info

    result = get_system_and_app_info(
        request=GetSystemAndAppInfoRequest(), app_context=app_context
    ).model_dump(mode="python")
    if result.get("status") == "success":
        return AppInfoResponse(
            status="success",
            info={
                **{k: v for k, v in result.items() if k != "status"},
                "timezone": app_context.settings.get("general.timezone", "UTC"),
            },
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.get("message", "Failed to retrieve system info."),
        )


@router.get(
    "/api/info/themes",
    operation_id="list_themes",
    tags=["Appearance"],
    response_model=ThemeListResponse,
)
@describe_access("public", authentication="none", additional_checks=[])
async def get_themes(
    app_context: AppContext = Depends(get_app_context),
) -> ThemeListResponse:
    """Return a list of available themes (standard and custom)."""
    logger.debug("Request for available themes.")
    STANDARD_THEMES = [
        "default",
        "light",
        "gradient",
        "black",
        "red",
        "green",
        "blue",
        "yellow",
        "pink",
    ]
    themes = set(STANDARD_THEMES)
    themes_path = app_context.settings.get("paths.themes")

    if themes_path and await aiofiles.ospath.isdir(themes_path):

        def list_themes():
            return os.listdir(themes_path)

        filenames = await asyncio.to_thread(list_themes)
        for filename in filenames:
            if filename.endswith(".css"):
                themes.add(filename[:-4])

    sorted_themes = sorted(list(themes))
    if "default" in sorted_themes:
        sorted_themes.remove("default")
        sorted_themes.insert(0, "default")

    return ThemeListResponse(status="success", themes=sorted_themes)


@router.get(
    "/api/metrics",
    operation_id="get_application_metrics",
    tags=["Application"],
    response_model=GetApplicationMetricsResponse,
)
async def get_application_metrics(
    current_user: UserResponse = Security(
        require_permissions, scopes=[Permission.RUNTIME_METRICS]
    ),
    app_context: AppContext = Depends(get_app_context),
) -> GetApplicationMetricsResponse:
    """Authenticated application and host performance observations."""
    return await system_api.get_application_metrics(
        GetApplicationMetricsRequest(), app_context=app_context
    )


@router.get(
    "/api/health",
    operation_id="get_application_health",
    tags=["Application"],
    response_model=GetApplicationHealthResponse,
    dependencies=[Depends(require_health_access)],
)
@describe_access(
    "custom",
    authentication="required",
    additional_checks=["local-readiness-or-account", "local-readiness-peer"],
)
async def get_application_health(
    request: Request,
    app_context: AppContext = Depends(get_app_context),
) -> GetApplicationHealthResponse:
    """Return health and process identity for a user or local supervisor."""
    health = await system_api.get_application_health(
        GetApplicationHealthRequest(), app_context=app_context
    )
    runtime = getattr(request.app.state, "web_runtime", None)
    if isinstance(runtime, WebRuntime):
        snapshot = runtime.snapshot()
        health = health.model_copy(update={"instance_id": snapshot.instance_id})
        if snapshot.phase != LifecyclePhase.READY:
            health = health.model_copy(
                update={
                    "ready": False,
                    "lifecycle": snapshot.phase,
                    "health": "degraded",
                    "checks": {
                        **health.checks,
                        "lifecycle": health.checks["lifecycle"].model_copy(
                            update={
                                "healthy": False,
                                "message": "Web runtime is not ready",
                            }
                        ),
                    },
                }
            )
    return health
