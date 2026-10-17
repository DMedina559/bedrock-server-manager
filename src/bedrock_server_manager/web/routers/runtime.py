"""HTTP control of the hosting runtime; no process spawning API."""

import ipaddress
from typing import Literal

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Request,
    Security,
)
from fastapi.security import APIKeyHeader

from ...api.models.health import GetApplicationHealthRequest, HealthCheck
from ...api.system import get_application_health
from ...config import get_installed_version
from ...context import AppContext
from ...error import DependencyUnavailableError
from ...services.lifecycle import LifecyclePhase
from ..deps import get_app_context
from ..deps.auth import get_admin_user, get_current_user_optional
from ..runtime import RuntimeStatus, ShutdownRequest, ShutdownResponse, WebRuntime
from ..schemas.runtime import RuntimeReadinessResponse

router = APIRouter(prefix="/api/runtime", tags=["Runtime"])
local_key = APIKeyHeader(name="X-BSM-Shutdown-Token", auto_error=False)
readiness_key = APIKeyHeader(name="X-BSM-Readiness-Token", auto_error=False)


def get_web_runtime(request: Request) -> WebRuntime:
    runtime = getattr(request.app.state, "web_runtime", None)
    if not isinstance(runtime, WebRuntime):
        raise DependencyUnavailableError(
            "This ASGI host does not expose lifecycle control"
        )
    return runtime


async def shutdown_actor(
    request: Request,
    token: str | None = Security(local_key),
    user=Security(get_current_user_optional),
) -> Literal["local_cli", "administrator"]:
    runtime = getattr(request.app.state, "web_runtime", None)
    if token is not None:
        if isinstance(runtime, WebRuntime) and runtime.authenticate_local(token):
            return "local_cli"
        raise HTTPException(status_code=401, detail="Invalid shutdown credential")
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Administrator permission required")
    return "administrator"


@router.get(
    "",
    operation_id="get_web_runtime",
    response_model=RuntimeStatus,
    dependencies=[Depends(get_admin_user)],
)
async def runtime_status(
    runtime: WebRuntime = Depends(get_web_runtime),
) -> RuntimeStatus:
    return runtime.snapshot()


@router.post(
    "/shutdown",
    operation_id="shutdown_web_runtime",
    status_code=202,
    response_model=ShutdownResponse,
)
async def shutdown_runtime(
    request: ShutdownRequest,
    background: BackgroundTasks,
    actor: Literal["local_cli", "administrator"] = Depends(shutdown_actor),
    runtime: WebRuntime = Depends(get_web_runtime),
) -> ShutdownResponse:
    receipt = runtime.accept_shutdown(actor)
    background.add_task(runtime.signal_exit)
    return receipt


async def require_local_readiness(
    request: Request,
    token: str | None = Security(readiness_key),
    runtime: WebRuntime = Depends(get_web_runtime),
) -> WebRuntime:
    """Require a local peer and a capability scoped to readiness."""
    peers = (request.scope.get("bsm.peer"), request.scope.get("client"))
    try:
        local = all(
            peer is not None and ipaddress.ip_address(peer[0]).is_loopback
            for peer in peers
        )
    except ValueError:
        local = False
    if not local:
        raise HTTPException(status_code=403, detail="Local readiness access required")
    if token is None or not runtime.authenticate_readiness(token):
        raise HTTPException(status_code=401, detail="Invalid readiness credential")
    return runtime


@router.get(
    "/readiness",
    operation_id="get_local_runtime_readiness",
    response_model=RuntimeReadinessResponse,
)
async def local_runtime_readiness(
    runtime: WebRuntime = Depends(require_local_readiness),
    app_context: AppContext = Depends(get_app_context),
) -> RuntimeReadinessResponse:
    """Return health and runtime identity without a user account."""
    health = await get_application_health(
        GetApplicationHealthRequest(), app_context=app_context
    )
    snapshot = runtime.snapshot()
    if snapshot.phase != LifecyclePhase.READY:
        health = health.model_copy(
            update={
                "ready": False,
                "lifecycle": snapshot.phase,
                "health": "degraded",
                "checks": {
                    **health.checks,
                    "lifecycle": HealthCheck(
                        healthy=False, message="Web runtime is not ready"
                    ),
                },
            }
        )
    return RuntimeReadinessResponse(
        runtime=snapshot,
        version=get_installed_version(),
        health=health,
    )
