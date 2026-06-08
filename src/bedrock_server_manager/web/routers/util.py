# bedrock_server_manager/web/routers/util.py
"""
Utility and miscellaneous web server routes for the Bedrock Server Manager.

This module provides FastAPI router endpoints for common utility functions,
such as serving static assets (custom panorama, world icons, favicon) and
handling catch-all routes for undefined paths. These endpoints often involve
file system interactions and fallbacks to default assets if custom ones are
not found.
"""

import logging
import os

import bsm_frontend
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from ...context import AppContext
from ...error import AppFileNotFoundError, BSMError, InvalidServerNameError
from ..dependencies import get_app_context, validate_server_exists

STATIC_DIR = bsm_frontend.get_static_dir()


logger = logging.getLogger(__name__)

router = APIRouter()


# --- Route: Serve Custom Panorama ---
@router.get("/api/panorama", response_class=FileResponse, tags=["Global Info API"])
async def serve_custom_panorama_api(
    app_context: AppContext = Depends(get_app_context),
):
    """Serves a custom `panorama.jpeg` background image if available, otherwise a default.

    This endpoint attempts to locate a `panorama.jpeg` file in the application's
    configuration directory. If found, it's served. If not, or if the config
    directory isn't set, it falls back to serving a default panorama image
    from the static assets.
    """
    logger.debug("Request received to serve custom panorama background.")
    try:
        config_dir = app_context.settings.config_dir
        if not config_dir:

            logger.error("Config directory not set in settings.")
            raise AppFileNotFoundError("CONFIG_DIR not set.", "Setting")

        custom_panorama_path = os.path.join(config_dir, "panorama.jpeg")
        if os.path.isfile(custom_panorama_path):
            logger.debug(f"Serving custom panorama from: {custom_panorama_path}")
            return FileResponse(custom_panorama_path, media_type="image/jpeg")
        else:
            logger.info("Custom panorama not found. Serving default.")
            raise AppFileNotFoundError(custom_panorama_path, "Custom Panorama")

    except AppFileNotFoundError:
        default_panorama_path = os.path.join(STATIC_DIR, "image", "panorama.jpeg")
        if os.path.isfile(default_panorama_path):
            logger.debug(f"Serving default panorama from: {default_panorama_path}")
            return FileResponse(default_panorama_path, media_type="image/jpeg")
        else:
            logger.error(f"Default panorama not found at {default_panorama_path}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Default panorama image not found.",
            )
    except Exception as e:
        logger.error(f"Unexpected error serving panorama: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error serving panorama image.",
        )


# --- Route: Serve World Icon ---
@router.get(
    "/api/server/{server_name}/world/icon",
    response_class=FileResponse,
    tags=["Server Info API"],
)
async def serve_world_icon_api(
    server_name: str = Depends(validate_server_exists),
    app_context: AppContext = Depends(get_app_context),
):
    """Serves the `world_icon.jpeg` for a server, or a default icon if not found.

    Retrieves the `world_icon.jpeg` associated with the specified server's world.
    If the server-specific icon doesn't exist or an error occurs (e.g., invalid
    server name), it falls back to serving a default icon (favicon.ico).
    """
    logger.debug(f"Request to serve world icon for server '{server_name}'.")
    try:
        server = app_context.get_server(server_name)
        icon_path = server.world_icon_filesystem_path

        if server.has_world_icon() and icon_path and os.path.isfile(icon_path):
            logger.debug(f"Serving world icon from path: {icon_path}")
            return FileResponse(icon_path, media_type="image/jpeg")
        else:

            logger.info(
                f"World icon for '{server_name}' not found at '{icon_path}'. Serving default."
            )
            raise AppFileNotFoundError(str(icon_path), "World icon")

    except (
        AppFileNotFoundError,
        InvalidServerNameError,
        BSMError,
    ) as e:
        if not isinstance(e, AppFileNotFoundError):
            logger.error(
                f"Error preparing to serve world icon for '{server_name}': {e}",
                exc_info=True,
            )

        default_icon_path = os.path.join(STATIC_DIR, "image", "icon", "favicon.ico")
        if os.path.isfile(default_icon_path):
            logger.debug(
                f"Serving default world icon (favicon.ico) from: {default_icon_path}"
            )
            return FileResponse(
                default_icon_path, media_type="image/vnd.microsoft.icon"
            )
        else:
            logger.error(
                f"Default world icon (favicon.ico) not found at {default_icon_path}"
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Default world icon not found.",
            )

    except Exception as e:
        logger.error(
            f"Unexpected error serving world icon for '{server_name}': {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error serving icon.",
        )


@router.get("/favicon.ico", include_in_schema=False)
async def get_root_favicon():
    """Serves the `favicon.ico` file from the static directory."""
    favicon_path = os.path.join(STATIC_DIR, "image", "icon", "favicon.ico")
    if not os.path.exists(favicon_path):
        # If the file genuinely doesn't exist, return a 404
        logger.warning(f"Favicon not found at expected path: {favicon_path}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Favicon not found"
        )
    # Return the file directly with the correct media type
    return FileResponse(favicon_path, media_type="image/x-icon")
