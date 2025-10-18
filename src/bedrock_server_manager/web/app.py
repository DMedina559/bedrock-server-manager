# bedrock_server_manager/web/app.py
import logging
import sys
import atexit
from pathlib import Path
import os
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from starlette.middleware.authentication import AuthenticationMiddleware

from ..context import AppContext
from ..config import get_installed_version
from . import routers
from ..config import bcm_config
from .auth_utils import CustomAuthBackend, get_current_user_optional


def create_web_app(app_context: AppContext) -> FastAPI:
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
        yield
        # Shutdown logic goes here
        logger.info("Running web app shutdown hooks...")
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

    from ..config import SCRIPT_DIR

    app_path = os.path.join(SCRIPT_DIR, "web", "app.py")
    APP_ROOT = os.path.dirname(os.path.abspath(app_path))
    STATIC_DIR = os.path.join(APP_ROOT, "static")
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

    app_context.plugin_manager.trigger_guarded_event("on_manager_startup")

    api.utils.update_server_statuses(app_context=app_context)

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    # Mount custom themes directory
    themes_path = settings.get("paths.themes")
    if os.path.isdir(themes_path):
        app.mount("/themes", StaticFiles(directory=themes_path), name="themes")

    @app.middleware("http")
    async def setup_check_middleware(request: Request, call_next):
        # Paths that should be accessible even if setup is not complete
        allowed_paths = [
            "/setup",
            "/static",
            "/favicon.ico",
            "/auth/token",
            "/docs",
            "/openapi.json",
        ]

        if bcm_config.needs_setup(request.app.state.app_context) and not any(
            request.url.path.startswith(p) for p in allowed_paths
        ):
            return RedirectResponse(url="/setup")

        # Manually handle authentication to bypass it for static files
        if not request.url.path.startswith("/static"):
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
