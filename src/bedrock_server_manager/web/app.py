# bedrock_server_manager/web/app.py
import asyncio
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
from . import routers

mimetypes.add_type("application/javascript", ".js")


def create_web_app(app_context: AppContext) -> FastAPI:  # noqa: C901
    """Creates and configures the web application."""
    logger = logging.getLogger(__name__)

    settings = app_context.settings
    plugin_manager = app_context.plugin_manager

    asyncio.run(plugin_manager.load_plugins())

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Startup logic goes here
        app_context = app.state.app_context
        try:
            app_context.loop = asyncio.get_running_loop()
            await app_context.bedrock_process_manager.start()
            app_context.resource_monitor.start()
            await app_context.api.application.update_server_statuses(request={})

            await app_context.plugin_manager.trigger_guarded_event("on_manager_startup")
            await app_context.plugin_manager.start_plugin_tasks()

            # Initialize and start LogStreamer
            log_streamer = app_context.log_streamer
            log_streamer.start()

            yield
        finally:
            # Shutdown logic goes here
            logger.info("Running web app shutdown hooks...")

            await app_context.shutdown()
            logger.info("Web app shutdown hooks complete.")

    version = get_installed_version()

    # --- FastAPI App Initialization ---
    app = FastAPI(
        title="Bedrock Server Manager",
        version=version,
        redoc_url=None,
        openapi_url="/api/openapi.json",
        swagger_ui_parameters={
            "defaultModelsExpandDepth": -1,
            "filter": True,
            "deepLinking": True,
        },
        lifespan=lifespan,
        responses={
            code: {"model": ErrorEnvelope}
            for code in (400, 401, 403, 404, 409, 422, 500)
        },
    )
    from fastapi.responses import JSONResponse
    from pydantic import ValidationError

    from ..api.errors import error_response
    from ..error import (
        APICancelledError,
        AppFileNotFoundError,
        BSMError,
        UserInputError,
    )
    from ..plugins.api_contract import APIResponseValidationError

    async def api_error_handler(request, error):
        headers = None
        if isinstance(error, RequestValidationError):
            status_code = 422
            payload = APIErrorResponse(
                code="validation_error",
                message="Invalid request.",
                details={
                    "errors": [
                        {"location": list(item["loc"]), "code": item["type"]}
                        for item in error.errors()
                    ]
                },
            )
        elif isinstance(error, StarletteHTTPException):
            status_code = error.status_code
            headers = error.headers
            code = {
                400: "validation_error",
                401: "unauthorized",
                403: "forbidden",
                404: "not_found",
                409: "conflict",
                422: "validation_error",
            }.get(status_code, "http_error")
            if status_code >= 500:
                code = "internal_error"
            message = (
                error.detail
                if isinstance(error.detail, str) and status_code < 500
                else "An unexpected error occurred."
            )
            payload = APIErrorResponse.model_validate(
                {"code": code, "message": message}
            )
        else:
            if isinstance(error, ValidationError):
                status_code = 422
            elif isinstance(error, AppFileNotFoundError):
                status_code = 404
            elif isinstance(error, APICancelledError):
                status_code = 409
            elif isinstance(error, UserInputError):
                status_code = 400
            else:
                status_code = 500
                logger.error("API operation failed", exc_info=error)
            payload = error_response(error)
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
    ):
        app.add_exception_handler(exception_type, api_error_handler)

    app.state.app_context = app_context

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

    logger.info(f"CORS Allowed Origins: {allowed_origins}")

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
            logger.info(f"Mounted bsm-frontend assets from {assets_subdir}")
        else:
            logger.warning(
                f"bsm-frontend 'assets' subdirectory not found at {assets_subdir}"
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
            logger.info(f"Mounted bsm-frontend images from {image_subdir}")
        else:
            logger.warning(
                f"bsm-frontend 'image' subdirectory not found at {image_subdir}"
            )

    else:
        logger.warning(f"bsm-frontend static directory not found at {static_dir}")

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
