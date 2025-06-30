import os
import logging
from typing import Dict, Any

import os
import logging
from typing import Dict, Any

from fastapi import APIRouter, Request, Depends, HTTPException, status, Path
from fastapi.responses import FileResponse, RedirectResponse

from bedrock_server_manager.web.auth_utils import (
    get_current_user,
    get_current_user_optional,
)
from ..dependencies import validate_server_exists
from bedrock_server_manager.core.bedrock_server import BedrockServer
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.error import (
    BSMError,
    AppFileNotFoundError,
    InvalidServerNameError,
)

WEB_APP_ROOT = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(WEB_APP_ROOT))
STATIC_DIR = os.path.join(os.path.dirname(WEB_APP_ROOT), "static")


logger = logging.getLogger(__name__)

router = APIRouter(tags=["Utilities"])


# --- Route: Serve Custom Panorama ---
@router.get("/api/panorama", response_class=FileResponse)
async def serve_custom_panorama_api():
    """Serves a custom `panorama.jpeg` background image if it exists, else default."""
    logger.debug("Request received to serve custom panorama background.")
    try:
        config_dir = settings.config_dir
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
@router.get("/api/server/{server_name}/world/icon", response_class=FileResponse)
async def serve_world_icon_api(
    server_name: str = Depends(validate_server_exists),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Serves the `world_icon.jpeg` file for a specific server's world, with fallback."""
    logger.debug(
        f"Request to serve world icon for server '{server_name}' by user '{current_user.get('username', 'Unknown')}'."
    )

    try:
        server = BedrockServer(server_name)
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
    """
    Handles the implicit browser request for /favicon.ico at the root.
    Serves the actual favicon.ico from the static directory.
    """
    favicon_path = os.path.join(STATIC_DIR, "image", "icon", "favicon.ico")
    if not os.path.exists(favicon_path):
        # If the file genuinely doesn't exist, return a 404
        logger.warning(f"Favicon not found at expected path: {favicon_path}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Favicon not found"
        )
    # Return the file directly with the correct media type
    return FileResponse(favicon_path, media_type="image/x-icon")


# --- Catch-all Route ---
@router.get("/{full_path:path}", name="catch_all_route", include_in_schema=False)
async def catch_all_api_route(
    request: Request,
    full_path: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Redirects any unmatched authenticated route to the main dashboard page."""
    logger.warning(
        f"User '{current_user.get('username', 'Unknown')}' accessed undefined path: '/{full_path}'. Redirecting to dashboard."
    )

    index_url = "/"
    return RedirectResponse(url=index_url)
