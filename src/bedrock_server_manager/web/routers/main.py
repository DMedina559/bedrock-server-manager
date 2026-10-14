# bedrock_server_manager/web/routers/main.py
"""
FastAPI router for the main web application.
"""

import html
import logging
import os
import re
from urllib.parse import quote

import aiofiles
import bsm_frontend
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

logger = logging.getLogger(__name__)

router = APIRouter(include_in_schema=False)


@router.get(
    "/",
    operation_id="root_redirect",
)
async def root_redirect(request: Request):
    """Redirects the root URL to dashboard."""
    # Build URL dynamically to respect root_path (e.g., behind Ingress)
    redirect_url = request.url_for("serve_spa")
    # Ensure it has a trailing slash for consistency if desired
    return RedirectResponse(url=str(redirect_url))


@router.get("/app", operation_id="serve_spa")
@router.get("/app/{full_path:path}", operation_id="serve_spa_path")
async def serve_spa(request: Request, full_path: str = ""):
    """Serves the SPA index.html for all /app routes, excluding assets."""

    if full_path.startswith("assets/"):
        raise HTTPException(status_code=404, detail="Asset not found")

    static_dir = bsm_frontend.get_static_dir()
    index_path = os.path.join(static_dir, "index.html")

    if os.path.exists(index_path):
        root_path = quote(request.scope.get("root_path", ""), safe="/-._~!$&'()*+,;=:@")
        async with aiofiles.open(index_path, "r", encoding="utf-8") as file:
            content = await file.read()
        # One same-origin base precedes all assets, also on direct deep links.
        base = html.escape(f"{root_path}/app/", quote=True)
        prefix = html.escape(root_path, quote=True)
        content = re.sub(r"<base\b[^>]*>", "", content, flags=re.IGNORECASE)
        content = content.replace(
            "<head>",
            f'<head>\n    <base id="app-asset-base" href="{base}" '
            f'data-api-base="{prefix}" />',
            1,
        )
        return HTMLResponse(content=content, headers={"Cache-Control": "no-store"})

    raise HTTPException(status_code=404, detail="Frontend not found.")
