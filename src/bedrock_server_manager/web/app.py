# bedrock_server_manager/web/app.py
import logging
import mimetypes
import os
from contextlib import asynccontextmanager
from typing import Any

import bsm_frontend
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from ..api.models.common import APIErrorResponse, ErrorEnvelope
from ..config import get_installed_version
from ..context import AppContext
from ..logging import log_operation_error
from ..services.lifecycle import LifecyclePhase
from . import routers
from .openapi_tags import OPENAPI_TAGS
from .runtime import WebRuntime

mimetypes.add_type("application/javascript", ".js")


def create_web_app(
    app_context: AppContext, runtime: WebRuntime | None = None
) -> FastAPI:  # noqa: C901
    """Create and configure the web application."""
    logger = logging.getLogger(__name__)

    settings = app_context.settings
    plugin_manager = app_context.plugin_manager

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        context = app.state.app_context
        await context.startup()
        try:
            if runtime is not None:
                runtime.ready()
            yield
        finally:
            try:
                await context.shutdown()
            except BaseException:
                if runtime is not None:
                    runtime.finish(failed=True)
                raise
            else:
                if runtime is not None:
                    runtime.finish()

    version = get_installed_version()

    # --- FastAPI App Initialization ---
    app = FastAPI(
        title="Bedrock Server Manager",
        version=version,
        redoc_url=None,
        openapi_url="/api/openapi.json",
        openapi_tags=OPENAPI_TAGS,
        swagger_ui_parameters={
            "defaultModelsExpandDepth": -1,
            "filter": True,
            "deepLinking": True,
        },
        lifespan=lifespan,
        responses={
            code: {"model": ErrorEnvelope}
            for code in (400, 401, 403, 404, 409, 422, 500, 503)
        },
    )
    from fastapi.responses import JSONResponse
    from pydantic import ValidationError

    from ..error import BSMError
    from ..failures import classify_failure
    from ..plugins.api_contract import APIResponseValidationError

    async def api_error_handler(request, error):
        headers = None
        classified = classify_failure(error)
        status_code = classified.status_code
        payload = APIErrorResponse.model_validate(classified.error.model_dump())
        headers = getattr(error, "headers", None)
        if not classified.expected:
            log_operation_error(
                logger,
                "HTTP operation failed: %s %s",
                request.method,
                request.url.path,
                error=error,
            )
        return JSONResponse(
            status_code=status_code,
            headers=headers,
            content=ErrorEnvelope(error=payload).model_dump(mode="json"),
        )

    for exception_type in (
        ValidationError,
        BSMError,
        APIResponseValidationError,
        RequestValidationError,
        ResponseValidationError,
        StarletteHTTPException,
        Exception,
    ):
        app.add_exception_handler(exception_type, api_error_handler)

    app.state.app_context = app_context
    app.state.web_runtime = runtime
    app_context._web_runtime = runtime

    @app.middleware("http")
    async def reject_new_mutations(request, call_next):
        control = getattr(app.state, "web_runtime", None)
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
            from ..error import DependencyUnavailableError

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

    # --- CORS Middleware ---
    # Allow configured origins or default to localhost for development/remote usage
    # Default to 3000 (React/CRA) and 5173 (Vite)
    default_origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    allowed_origins = app_context.get_pre_app_config(
        "web.cors_origins", default_origins
    )

    # If user provided a string (e.g. "*"), wrap it in a list
    if isinstance(allowed_origins, str):
        allowed_origins = [allowed_origins]

    if not isinstance(allowed_origins, list):
        allowed_origins = []

    # allow_credentials=True cannot be used with allow_origins=["*"] in CORS.
    # If "*" is present, we use allow_origin_regex=".*" to dynamically reflect the origin.
    allow_all_origins = "*" in allowed_origins

    logger.debug("CORS Allowed Origins: %s", allowed_origins)

    from .middleware.static import IngressAwareStaticFiles

    # --- Mount Static Assets from bsm-frontend ---
    static_dir = bsm_frontend.get_static_dir()

    if os.path.isdir(static_dir):
        # Explicitly check for 'assets' and 'image' subdirectories before mounting
        assets_subdir = os.path.join(static_dir, "assets")
        image_subdir = os.path.join(static_dir, "image")

        if os.path.isdir(assets_subdir):
            app.mount(
                "/app/assets",
                IngressAwareStaticFiles(directory=assets_subdir),
                name="app_assets",
            )
            logger.debug("Mounted bsm-frontend assets from %s", assets_subdir)
        else:
            logger.warning(
                "bsm-frontend 'assets' subdirectory not found at %s", assets_subdir
            )

        if os.path.isdir(image_subdir):
            app.mount(
                "/app/image",
                IngressAwareStaticFiles(directory=image_subdir),
                name="app_images",
            )
            app.mount(
                "/image",
                IngressAwareStaticFiles(directory=image_subdir),
                name="root_images",
            )
            logger.debug("Mounted bsm-frontend images from %s", image_subdir)
        else:
            logger.warning(
                "bsm-frontend 'image' subdirectory not found at %s", image_subdir
            )

    else:
        logger.warning("bsm-frontend static directory not found at %s", static_dir)

    # Mount custom themes directory
    themes_path = settings.get("paths.themes")
    if os.path.isdir(themes_path):
        app.mount(
            "/themes", IngressAwareStaticFiles(directory=themes_path), name="themes"
        )

    from .middleware.auth import add_user_to_request
    from .middleware.setup import setup_check_middleware

    app.middleware("http")(setup_check_middleware)
    app.middleware("http")(add_user_to_request)

    # Add CORS Middleware
    cors_kwargs: dict[str, Any] = {
        "allow_credentials": True,
        "allow_methods": ["*"],
        "allow_headers": ["*"],
    }

    if allow_all_origins:
        cors_kwargs["allow_origin_regex"] = ".*"
    else:
        cors_kwargs["allow_origins"] = allowed_origins

    app.add_middleware(CORSMiddleware, **cors_kwargs)

    # Add ASGI middleware for Ingress support (executes first)
    from .middleware.ingress import IngressMiddleware

    app.add_middleware(IngressMiddleware)

    for router in routers.all_routers:
        app.include_router(router)

    plugin_manager.bind_web_app(app)

    return app
