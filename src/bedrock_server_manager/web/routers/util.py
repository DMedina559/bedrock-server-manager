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

import aiofiles.ospath
import bsm_frontend
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from ...context import AppContext
from ...error import AppFileNotFoundError
from ...logging import log_operation_error
from ..deps import get_app_context

STATIC_DIR = bsm_frontend.get_static_dir()


logger = logging.getLogger(__name__)

router = APIRouter()


# --- Route: Serve Custom Panorama ---
@router.get(
    "/api/panorama",
    operation_id="get_panorama",
    response_class=FileResponse,
    tags=["Application"],
)
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
        if await aiofiles.ospath.isfile(custom_panorama_path):
            logger.debug("Serving custom panorama from: %s", custom_panorama_path)
            return FileResponse(custom_panorama_path, media_type="image/jpeg")
        else:
            logger.debug("Custom panorama not found. Serving default.")
            raise AppFileNotFoundError(custom_panorama_path, "Custom Panorama")

    except AppFileNotFoundError:
        default_panorama_path = os.path.join(STATIC_DIR, "image", "panorama.jpeg")
        if await aiofiles.ospath.isfile(default_panorama_path):
            logger.debug("Serving default panorama from: %s", default_panorama_path)
            return FileResponse(default_panorama_path, media_type="image/jpeg")
        else:
            logger.error("Default panorama not found at %s", default_panorama_path)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Default panorama image not found.",
            )
    except HTTPException:
        raise
    except Exception as e:
        log_operation_error(logger, "Unexpected error serving panorama: %s", e, error=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error serving panorama image.",
        )
