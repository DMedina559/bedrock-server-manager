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
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os

from bedrock_server_manager.web import templating
from bedrock_server_manager.config.const import get_installed_version

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

from bedrock_server_manager.web.routers import (
    main,
    auth,
    schedule_tasks,
    server_actions,
    server_install_config,
    backup_restore,
    content,
    util,
    settings,
    api_info,
    plugin,
)

app.include_router(main.router)
app.include_router(auth.router)
app.include_router(schedule_tasks.router)
app.include_router(server_actions.router)
app.include_router(server_install_config.router)
app.include_router(backup_restore.router)
app.include_router(content.router)
app.include_router(settings.router)
app.include_router(api_info.router)
app.include_router(plugin.router) # Core plugin management UI routes
app.include_router(util.router)


# --- Dynamically include FastAPI routers from plugins ---
# This section runs when web/main.py is imported (e.g., by Uvicorn).
# It needs access to a PluginManager instance that has already loaded plugins.

# Import necessary modules (ideally, these would be less deep if possible, or PluginManager could be a singleton)
from bedrock_server_manager.config.settings import Settings as GlobalSettings # Alias to avoid conflict if any
from bedrock_server_manager.plugins.plugin_manager import PluginManager as GlobalPluginManager # Alias
import logging # Use standard logging

web_main_logger = logging.getLogger("bsm_web_main") # Specific logger for this module

try:
    # Instantiate settings if not already available globally in a way this module can see.
    # PluginManager relies on the global `settings` from `config.settings` when it's imported.
    # So, ensuring `config.settings.settings` is initialized is key.
    # `GlobalSettings()` call ensures it's loaded if not already.
    _ = GlobalSettings() # Ensures settings are loaded for PluginManager

    pm_instance = GlobalPluginManager()
    pm_instance.load_plugins() # Load plugins and collect their routers

    if pm_instance.plugin_fastapi_routers:
        web_main_logger.info(
            f"Found {len(pm_instance.plugin_fastapi_routers)} FastAPI router(s) from plugins. Attempting to include them."
        )
        for router_idx, router_obj in enumerate(pm_instance.plugin_fastapi_routers):
            try:
                # Basic check if it's an APIRouter, can be made more robust
                if hasattr(router_obj, "routes") and callable(getattr(router_obj, "include_router", None)):
                    app.include_router(router_obj)
                    router_prefix = getattr(router_obj, 'prefix', f"N/A_idx_{router_idx}")
                    web_main_logger.info(f"Successfully included FastAPI router with prefix '{router_prefix}' from a plugin.")
                else:
                    web_main_logger.warning(
                        f"Plugin provided an object that does not appear to be a valid FastAPI APIRouter at index {router_idx}. Object: {type(router_obj)}"
                    )
            except Exception as e_router:
                web_main_logger.error(
                    f"Failed to include a FastAPI router (index {router_idx}) from a plugin: {e_router}", exc_info=True
                )
    else:
        web_main_logger.info("No additional FastAPI routers found from plugins to include.")

except ImportError as e_imp:
    web_main_logger.critical(
        f"Could not import Settings or PluginManager for FastAPI plugin integration: {e_imp}. Plugin web endpoints will be disabled.",
        exc_info=True
    )
except Exception as e_plugin_load:
    web_main_logger.critical(
        f"Critical error during plugin FastAPI router integration: {e_plugin_load}. Plugin web endpoints may be disabled.",
        exc_info=True
    )
    # Depending on severity, one might re-raise to prevent app startup,
    # but for now, we allow the app to try starting without plugin routers.


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=11325)
