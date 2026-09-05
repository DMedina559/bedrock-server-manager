# bedrock_server_manager/web/app.py
import asyncio
import logging
import mimetypes
import os
from contextlib import asynccontextmanager
from typing import Any

import bsm_frontend
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from ..config import get_installed_version
from ..context import AppContext
from . import routers

mimetypes.add_type("application/javascript", ".js")


def create_web_app(app_context: AppContext) -> FastAPI:  # noqa: C901
    """Creates and configures the web application."""
    logger = logging.getLogger(__name__)

    settings = app_context.settings
    plugin_manager = app_context.plugin_manager

    plugin_manager.load_plugins()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Startup logic goes here
        app_context = app.state.app_context
        app_context.loop = asyncio.get_running_loop()
        app_context.resource_monitor.start()
        await asyncio.to_thread(app_context.api.update_server_statuses)

        app_context.plugin_manager.trigger_guarded_event("on_manager_startup")
        app_context.plugin_manager.start_plugin_tasks()

        # Initialize and start LogStreamer
        from .log_streamer import LogStreamer

        log_streamer = LogStreamer(app_context)
        app_context.log_streamer = log_streamer
        log_streamer.start()

        yield
        # Shutdown logic goes here
        logger.info("Running web app shutdown hooks...")

        if hasattr(app_context, "log_streamer"):
            app_context.log_streamer.stop()

        app_context.resource_monitor.stop()

        # Shut down the process manager gracefully
        if (
            hasattr(app_context, "_bedrock_process_manager")
            and app_context._bedrock_process_manager is not None
        ):
            await app_context.bedrock_process_manager.shutdown()

        # Shut down the plugin manager gracefully
        if (
            hasattr(app_context, "_plugin_manager")
            and app_context._plugin_manager is not None
        ):
            await app_context.plugin_manager.shutdown()

        # Shut down the task manager gracefully
        if (
            hasattr(app_context, "_task_manager")
            and app_context._task_manager is not None
        ):
            await app_context.task_manager.shutdown()

        # Shut down the connection manager gracefully
        if (
            hasattr(app_context, "_connection_manager")
            and app_context._connection_manager is not None
        ):
            await app_context.connection_manager.shutdown()

        await app_context.db.shutdown()
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

    return app
