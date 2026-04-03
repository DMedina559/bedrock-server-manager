# bedrock_server_manager/web/app.py
import asyncio
import logging
import mimetypes
import os
from contextlib import asynccontextmanager

import bsm_frontend
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from ..config import bcm_config, get_installed_version
from ..context import AppContext
from . import routers
from .auth_utils import CustomAuthBackend, get_current_user_optional

mimetypes.add_type("application/javascript", ".js")


def create_web_app(app_context: AppContext) -> FastAPI:  # noqa: C901
    """Creates and configures the web application."""
    logger = logging.getLogger(__name__)
    from .. import api

    settings = app_context.settings
    plugin_manager = app_context.plugin_manager

    plugin_manager.load_plugins()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Startup logic goes here
        app_context = app.state.app_context
        app_context.loop = asyncio.get_running_loop()
        app_context.resource_monitor.start()

        # Initialize and start LogStreamer
        from .log_streamer import LogStreamer

        log_streamer = LogStreamer(app_context)
        # We store it in app_context to keep it alive and accessible if needed
        app_context.log_streamer = log_streamer
        log_streamer.start()

        yield
        # Shutdown logic goes here
        logger.info("Running web app shutdown hooks...")

        if hasattr(app_context, "log_streamer"):
            app_context.log_streamer.stop()

        app_context.resource_monitor.stop()
        # Shut down the task manager gracefully
        if (
            hasattr(app_context, "_task_manager")
            and app_context._task_manager is not None
        ):
            app_context.task_manager.shutdown()
        api.utils.stop_all_servers(app_context=app_context)
        app_context.plugin_manager.unload_plugins()
        app_context.db.close()
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
    )
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
    allowed_origins = bcm_config.get_config_value("web.cors_origins", default_origins)

    # If user provided a string (e.g. "*"), wrap it in a list
    if isinstance(allowed_origins, str):
        allowed_origins = [allowed_origins]

    if not isinstance(allowed_origins, list):
        allowed_origins = []

    logger.info(f"CORS Allowed Origins: {allowed_origins}")

    app_context.plugin_manager.trigger_guarded_event("on_manager_startup")

    api.utils.update_server_statuses(app_context=app_context)

    # --- Mount Static Assets from bsm-frontend ---
    static_dir = bsm_frontend.get_static_dir()

    if os.path.isdir(static_dir):
        # Explicitly check for 'assets' and 'image' subdirectories before mounting
        assets_subdir = os.path.join(static_dir, "assets")
        image_subdir = os.path.join(static_dir, "image")

        if os.path.isdir(assets_subdir):
            app.mount(
                "/app/assets", StaticFiles(directory=assets_subdir), name="app_assets"
            )
            logger.info(f"Mounted bsm-frontend assets from {assets_subdir}")
        else:
            logger.warning(
                f"bsm-frontend 'assets' subdirectory not found at {assets_subdir}"
            )

        if os.path.isdir(image_subdir):
            app.mount(
                "/app/image", StaticFiles(directory=image_subdir), name="app_images"
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
        app.mount("/themes", StaticFiles(directory=themes_path), name="themes")

    @app.middleware("http")
    async def setup_check_middleware(request: Request, call_next):
        # Paths that should be accessible even if setup is not complete
        allowed_paths = [
            "/setup/status",  # API status check
            "/setup/create-first-user",  # API create user
            "/app",  # The SPA itself
            "/themes",
            "/favicon.ico",
            "/auth/token",
            "/docs",
            "/openapi.json",
        ]

        # Allow static assets to pass through
        if request.url.path.startswith("/app/assets") or request.url.path.startswith(
            "/app/image"
        ):
            response = await call_next(request)
            return response

        if bcm_config.needs_setup(request.app.state.app_context) and not any(
            request.url.path.startswith(p) for p in allowed_paths
        ):

            if request.url.path.startswith("/api"):
                pass
            elif not request.url.path.startswith("/app"):
                return RedirectResponse(url="/app")

        # Manually handle authentication to bypass it for static files
        if not (
            request.url.path.startswith("/app/assets")
            or request.url.path.startswith("/app/image")
            or request.url.path.startswith("/themes")
        ):
            auth_backend = CustomAuthBackend()
            auth_result = await auth_backend.authenticate(request)
            if auth_result:
                creds, user = auth_result
                request.state.user = user
            else:
                request.state.user = None

        response = await call_next(request)
        return response

    @app.middleware("http")
    async def add_user_to_request(request: Request, call_next):
        user = await get_current_user_optional(request)
        request.state.current_user = user
        response = await call_next(request)
        return response

    # Add CORS Middleware last so it is the outermost middleware (executes first)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(routers.setup_router)
    app.include_router(routers.auth_router)
    app.include_router(routers.users_router)
    app.include_router(routers.register_router)
    app.include_router(routers.server_actions_router)
    app.include_router(routers.server_install_config_router)
    app.include_router(routers.backup_restore_router)
    app.include_router(routers.content_router)
    app.include_router(routers.settings_router)
    app.include_router(routers.api_info_router)
    app.include_router(routers.plugin_router)
    app.include_router(routers.tasks_router)
    app.include_router(routers.main_router)
    app.include_router(routers.account_router)
    app.include_router(routers.audit_log_router)
    app.include_router(routers.server_settings_router)
    app.include_router(routers.websocket_router)
    app.include_router(routers.spa_router)

    # --- Dynamically include FastAPI routers from plugins ---
    if plugin_manager.plugin_fastapi_routers:
        logger.info(
            f"Found {len(plugin_manager.plugin_fastapi_routers)} FastAPI router(s) from plugins. Attempting to include them."
        )
        for i, router in enumerate(plugin_manager.plugin_fastapi_routers):
            try:
                if hasattr(router, "routes"):
                    app.include_router(router)
                    logger.info(
                        f"Successfully included FastAPI router (prefix: '{router.prefix}') from a plugin."
                    )
                else:
                    logger.warning(
                        f"Plugin provided an object at index {i} that is not a valid FastAPI APIRouter."
                    )
            except Exception as e:
                logger.error(
                    f"Failed to include a FastAPI router from a plugin: {e}",
                    exc_info=True,
                )
    else:
        logger.info("No additional FastAPI routers found from plugins.")

    # --- Dynamically mount static directories from plugins ---
    if plugin_manager.plugin_static_mounts:
        logger.info(
            f"Found {len(plugin_manager.plugin_static_mounts)} static mount configurations from plugins."
        )
        for mount_path, dir_path, name in plugin_manager.plugin_static_mounts:
            try:
                app.mount(mount_path, StaticFiles(directory=dir_path), name=name)
                logger.info(
                    f"Mounted static directory '{dir_path}' at '{mount_path}' (name: '{name}')."
                )
            except Exception as e:
                logger.error(
                    f"Failed to mount static directory '{dir_path}' at '{mount_path}': {e}",
                    exc_info=True,
                )

    app.include_router(routers.util_router)

    return app
