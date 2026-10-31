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

from ...error import DependencyUnavailableError
from ..access_metadata import describe_access
from ..access_policy import Permission
from ..deps.auth import get_current_user_optional, require_permissions
from ..runtime import RuntimeStatus, ShutdownRequest, ShutdownResponse, WebRuntime

router = APIRouter(prefix="/api/runtime", tags=["Runtime"])
local_key = APIKeyHeader(name="X-BSM-Shutdown-Token", auto_error=False)
readiness_key = APIKeyHeader(
    name="X-BSM-Readiness-Token", scheme_name="LocalReadiness", auto_error=False
)


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
    dependencies=[Security(require_permissions, scopes=[Permission.RUNTIME_READ])],
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
@describe_access(
    "custom",
    authentication="required",
    additional_checks=["administrator-or-local-shutdown-token"],
    allowed_roles=["admin"],
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


async def require_health_access(
    request: Request,
    token: str | None = Security(readiness_key),
    user=Security(get_current_user_optional),
) -> None:
    """Accept a user credential or the scoped local readiness capability."""
    if token is None:
        if user is None:
            raise HTTPException(
                status_code=401,
                detail="Not authenticated",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return
    runtime = getattr(request.app.state, "web_runtime", None)
    if not isinstance(runtime, WebRuntime):
        raise DependencyUnavailableError(
            "This ASGI host does not expose local readiness"
        )
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
    if not runtime.authenticate_readiness(token):
        raise HTTPException(status_code=401, detail="Invalid readiness credential")
