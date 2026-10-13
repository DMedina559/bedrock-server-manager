"""Reject new mutations while the web runtime is stopping."""

from fastapi.responses import JSONResponse

from ...api.models.common import APIErrorResponse, ErrorEnvelope
from ...error import DependencyUnavailableError
from ...failures import classify_failure
from ...services.lifecycle import LifecyclePhase
from ..runtime import WebRuntime


async def reject_new_mutations(request, call_next):
    control = getattr(request.app.state, "web_runtime", None)
    path = request.scope.get("path", "")
    root = request.scope.get("root_path", "")
    if root and path.startswith(root):
        path = path[len(root) :]  # noqa: E203
    if (
        isinstance(control, WebRuntime)
        and control.snapshot().phase == LifecyclePhase.STOPPING
        and request.method in {"POST", "PUT", "PATCH", "DELETE"}
        and path.startswith("/api/")
        and path != "/api/runtime/shutdown"
    ):
        failure = classify_failure(
            DependencyUnavailableError("Web runtime is shutting down")
        )
        return JSONResponse(
            status_code=503,
            content=ErrorEnvelope(
                error=APIErrorResponse.model_validate(failure.error.model_dump())
            ).model_dump(mode="json"),
        )
    return await call_next(request)
