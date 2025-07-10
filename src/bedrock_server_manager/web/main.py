# bedrock_server_manager/web/main.py
"""
Main application file for the Bedrock Server Manager web UI.

This module initializes the :class:`fastapi.FastAPI` application instance,
mounts the static files directory, configures the Jinja2 templating environment
by calling :func:`~.templating.configure_templates`, and includes all API
and page routers from the ``web.routers`` package.

It serves as the central point for constructing the web application, preparing
it to be run by an ASGI server like Uvicorn. The Uvicorn server is also
started here if the script is run directly.
"""
from sys import version
import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import templating
from ..config import get_installed_version

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(APP_ROOT, "templates")
STATIC_DIR = os.path.join(APP_ROOT, "static")
version = get_installed_version()

app = FastAPI(
    title="Bedrock Server Manager",
    version=version,
    redoc_url=None,
    openapi_url="/api/openapi.json",
    swagger_ui_parameters={
        "defaultModelsExpandDepth": -1,  # Hide models section by default
        "filter": True,  # Enable filtering for operations
        "deepLinking": True,  # Enable deep linking for tags and operations
    },
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

_templates_instance = Jinja2Templates(directory=TEMPLATES_DIR)

templating.configure_templates(_templates_instance)

from . import routers

app.include_router(routers.main_router)
app.include_router(routers.auth_router)
app.include_router(routers.schedule_tasks_router)
app.include_router(routers.server_actions_router)
app.include_router(routers.server_install_config_router)
app.include_router(routers.backup_restore_router)
app.include_router(routers.content_router)
app.include_router(routers.settings_router)
app.include_router(routers.api_info_router)
app.include_router(routers.plugin_router)
app.include_router(routers.util_router)


# --- Dynamically include FastAPI routers from plugins ---

import logging  # Use standard logging

# Import the shared plugin_manager from the api module
try:
    from .. import plugin_manager as global_api_plugin_manager
except ImportError as e_imp_pm_web:
    # Fallback or error logging if it cannot be imported
    # This should ideally not happen if the application structure is correct
    # and api.__init__.py has done its job.
    logging.getLogger("bsm_web_main_plugin_loader").critical(
        f"CRITICAL: Could not import global_api_plugin_manager from bedrock_server_manager.api: {e_imp_pm_web}. "
        "Plugin FastAPI extensions will be unavailable.",
        exc_info=True,
    )
    global_api_plugin_manager = None


web_main_plugin_logger = logging.getLogger(
    "bsm_web_main_plugin_loader"
)  # Specific logger

if (
    global_api_plugin_manager
    and hasattr(global_api_plugin_manager, "plugin_fastapi_routers")
    and global_api_plugin_manager.plugin_fastapi_routers
):
    web_main_plugin_logger.info(
        f"Found {len(global_api_plugin_manager.plugin_fastapi_routers)} FastAPI router(s) "
        "from plugins via bedrock_server_manager.api.plugin_manager. Attempting to include them."
    )
    for router_idx, router_obj in enumerate(
        global_api_plugin_manager.plugin_fastapi_routers
    ):
        try:
            # Basic check if it's an APIRouter (can be made more robust)
            if hasattr(router_obj, "routes") and callable(
                getattr(router_obj, "include_router", None)
            ):  # Heuristic check
                app.include_router(router_obj)
                router_prefix = getattr(router_obj, "prefix", f"N/A_idx_{router_idx}")
                web_main_plugin_logger.info(
                    f"Successfully included FastAPI router with prefix '{router_prefix}' from a plugin."
                )
            else:
                web_main_plugin_logger.warning(
                    f"Plugin provided an object that does not appear to be a valid FastAPI APIRouter at index {router_idx}. Object type: {type(router_obj)}"
                )
        except Exception as e_router:
            web_main_plugin_logger.error(
                f"Failed to include a FastAPI router (index {router_idx}) from a plugin: {e_router}",
                exc_info=True,
            )
elif global_api_plugin_manager:
    web_main_plugin_logger.info(
        "No additional FastAPI routers found from plugins via bedrock_server_manager.api.plugin_manager."
    )
else:
    # This case implies global_api_plugin_manager import failed or it's None.
    web_main_plugin_logger.error(
        "global_api_plugin_manager is None or unavailable. Cannot include FastAPI routers from plugins. "
        "Check logs for import errors related to 'bedrock_server_manager.api.plugin_manager'."
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=11325)
