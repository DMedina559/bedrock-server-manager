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
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

import logging

from . import templating
from ..config import get_installed_version
from ..instances import get_plugin_manager_instance


APP_ROOT = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(APP_ROOT, "templates")  # This is a string path
STATIC_DIR = os.path.join(APP_ROOT, "static")
version = get_installed_version()

# --- Setup Template Directories ---
# Start with the main application's template directory
all_template_dirs = [Path(TEMPLATES_DIR)]

web_main_templating_logger = logging.getLogger("bsm_web_main_templating_setup")

global_api_plugin_manager = get_plugin_manager_instance()

if global_api_plugin_manager and hasattr(
    global_api_plugin_manager, "plugin_template_paths"
):
    if global_api_plugin_manager.plugin_template_paths:
        web_main_templating_logger.info(
            f"Adding {len(global_api_plugin_manager.plugin_template_paths)} template paths from plugins."
        )
        # Ensure paths are unique and are Path objects
        unique_plugin_paths = {
            p
            for p in global_api_plugin_manager.plugin_template_paths
            if isinstance(p, Path)
        }
        all_template_dirs.extend(list(unique_plugin_paths))
    else:
        web_main_templating_logger.info(
            "No additional template paths found from plugins."
        )
else:
    web_main_templating_logger.warning(
        "global_api_plugin_manager or its plugin_template_paths attribute is unavailable. "
        "Only main app templates will be loaded."
    )

# Ensure all paths are strings for Jinja2Templates if it doesn't handle Path objects directly (it should, but being safe)
# Jinja2Templates directory argument can be a str or a list of str/Path.
# Using Path objects directly is fine.
web_main_templating_logger.info(
    f"Configuring Jinja2 environment with directories: {all_template_dirs}"
)
templating.configure_templates(all_template_dirs)


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
# Mount custom themes directory
from ..instances import get_settings_instance

themes_path = get_settings_instance().get("paths.themes")
if os.path.isdir(themes_path):
    app.mount("/themes", StaticFiles(directory=themes_path), name="themes")

from . import routers

app.include_router(routers.main_router)
app.include_router(routers.auth_router)
app.include_router(routers.server_actions_router)
app.include_router(routers.server_install_config_router)
app.include_router(routers.backup_restore_router)
app.include_router(routers.content_router)
app.include_router(routers.settings_router)
app.include_router(routers.api_info_router)
app.include_router(routers.plugin_router)
app.include_router(routers.tasks_router)


# --- Dynamically include FastAPI routers from plugins ---

import logging  # Use standard logging


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

# --- Dynamically mount static directories from plugins ---
if (
    global_api_plugin_manager
    and hasattr(global_api_plugin_manager, "plugin_static_mounts")
    and global_api_plugin_manager.plugin_static_mounts
):
    web_main_plugin_logger.info(
        f"Found {len(global_api_plugin_manager.plugin_static_mounts)} static mount configurations "
        "from plugins. Attempting to mount them."
    )
    for mount_path, dir_path, name in global_api_plugin_manager.plugin_static_mounts:
        try:
            app.mount(mount_path, StaticFiles(directory=dir_path), name=name)
            web_main_plugin_logger.info(
                f"Successfully mounted static directory '{dir_path}' at '{mount_path}' with name '{name}' from a plugin."
            )
        except Exception as e_static_mount:
            web_main_plugin_logger.error(
                f"Failed to mount static directory '{dir_path}' at '{mount_path}' (name: '{name}') from a plugin: {e_static_mount}",
                exc_info=True,
            )
elif global_api_plugin_manager:
    web_main_plugin_logger.info("No additional static mounts found from plugins.")
# No else here, as the error for global_api_plugin_manager being unavailable is already logged above.

app.include_router(routers.util_router)


if __name__ == "__main__":
    import uvicorn
    from uvicorn.config import LOGGING_CONFIG

    # To prevent uvicorn from taking over the logger, we need to disable it.
    # More info: https://github.com/encode/uvicorn/issues/1285
    LOGGING_CONFIG["loggers"]["uvicorn"]["propagate"] = True

    uvicorn.run(app, host="127.0.0.1", port=11325, log_config=LOGGING_CONFIG)
