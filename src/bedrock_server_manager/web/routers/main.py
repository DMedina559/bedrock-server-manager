# bedrock_server_manager/web/routers/main.py
"""
FastAPI router for the main web application.
"""

import logging

from fastapi import APIRouter
from fastapi.responses import RedirectResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", include_in_schema=False)
async def root_redirect():
    """Redirects the root URL to the v2 dashboard."""
    return RedirectResponse(url="/app/")


# --- Legacy Routes Moved to legacy.py ---
