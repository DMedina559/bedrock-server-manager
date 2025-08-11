import logging
import sys
import atexit
from pathlib import Path
import os

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from starlette.middleware.authentication import AuthenticationMiddleware

from ..context import AppContext
from ..db import database
from . import templating
from ..config import get_installed_version
from . import routers
from .dependencies import needs_setup
from .auth_utils import CustomAuthBackend, get_current_user_optional


def create_web_app(app_context: AppContext) -> FastAPI:
    """Creates and configures the web application."""
    logger = logging.getLogger(__name__)
    from .. import api

    settings = app_context.settings
    plugin_manager = app_context.plugin_manager

    # Define shutdown hooks here to capture the plugin_manager instance
    def shutdown_web_app():
        logger.info("Running web app shutdown hooks...")
        api.utils.stop_all_servers(app_context=app_context)
        app_context.plugin_manager.unload_plugins()
        if database.engine:
            database.engine.dispose()
        logger.info("Web app shutdown hooks complete.")

    atexit.register(shutdown_web_app)
    plugin_manager.load_plugins()

    from ..config import SCRIPT_DIR

    app_path = os.path.join(SCRIPT_DIR, "web", "app.py")
    APP_ROOT = os.path.dirname(os.path.abspath(app_path))
    TEMPLATES_DIR = os.path.join(APP_ROOT, "templates")
    STATIC_DIR = os.path.join(APP_ROOT, "static")
    version = get_installed_version()

    # --- Template Directories Setup ---
    all_template_dirs = [Path(TEMPLATES_DIR)]
    if plugin_manager.plugin_template_paths:
        logger.info(
            f"Adding {len(plugin_manager.plugin_template_paths)} template paths from plugins."
        )
        unique_plugin_paths = {
            p for p in plugin_manager.plugin_template_paths if isinstance(p, Path)
        }
        all_template_dirs.extend(list(unique_plugin_paths))
    logger.info(f"Configuring Jinja2 with directories: {all_template_dirs}")
    templating.configure_templates(all_template_dirs, settings)

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
        if (
            await needs_setup()
            and not request.url.path.startswith("/setup")
            and not request.url.path.startswith("/static")
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
