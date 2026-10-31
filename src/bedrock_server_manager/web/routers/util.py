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
from ..access_metadata import describe_access
from ..deps import get_app_context

# bedrock_server_manager/web/routers/util.py


STATIC_DIR = bsm_frontend.get_static_dir()


logger = logging.getLogger(__name__)

router = APIRouter(tags=["Appearance"])


# --- Route: Serve Custom Panorama ---
# --- Route: Serve Custom Panorama ---
@router.get(
    "/api/panorama",
    operation_id="get_panorama",
    response_class=FileResponse,
)
@describe_access("public", authentication="none", additional_checks=[])
async def serve_custom_panorama_api(
    app_context: AppContext = Depends(get_app_context),
):
    """Serves a custom panorama background image if available, otherwise a default.

    This endpoint attempts to locate a ``panorama.(jpeg|jpg|png|webp)`` file in the
    application's configuration directory. If found, it's served. If not, or if the
    config directory isn't set, it falls back to serving a default panorama image from
    the static assets.
    """
    logger.debug("Request received to serve custom panorama background.")
    config_dir = app_context.settings.config_dir
    if config_dir:
        # Check supported file types in order of preference
        candidate_files = [
            ("panorama.jpeg", "image/jpeg"),
            ("panorama.jpg", "image/jpeg"),
            ("panorama.png", "image/png"),
            ("panorama.webp", "image/webp"),
        ]
        for filename, media_type in candidate_files:
            candidate_path = os.path.join(config_dir, filename)
            if await aiofiles.ospath.isfile(candidate_path):
                logger.debug("Serving custom panorama from: %s", candidate_path)
                return FileResponse(candidate_path, media_type=media_type)
    else:
        logger.warning("Config directory not set in settings.")

    # Fallback to default asset if no custom panorama was found or config_dir is missing
    default_panorama_path = os.path.join(STATIC_DIR, "image", "panorama.png")
    if await aiofiles.ospath.isfile(default_panorama_path):
        logger.debug("Serving default panorama from: %s", default_panorama_path)
        return FileResponse(default_panorama_path, media_type="image/png")

    logger.error("Default panorama not found at %s", default_panorama_path)
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Default panorama image not found.",
    )
