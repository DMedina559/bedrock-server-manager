# bedrock_server_manager/web/routers/main.py
"""
FastAPI router for the main web application.
"""

import logging
import os

import bsm_frontend
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse

logger = logging.getLogger(__name__)

router = APIRouter(include_in_schema=False)


@router.get(
    "/",
)
async def root_redirect(request: Request):
    """Redirects the root URL to dashboard."""
    # Build URL dynamically to respect root_path (e.g., behind Ingress)
    redirect_url = request.url_for("serve_spa")
    # Ensure it has a trailing slash for consistency if desired
    return RedirectResponse(url=str(redirect_url))


@router.get("/app")
@router.get("/app/{full_path:path}")
async def serve_spa(request: Request, full_path: str = ""):
    """Serves the SPA index.html for all /app routes, excluding assets."""

    if full_path.startswith("assets/"):
        raise HTTPException(status_code=404, detail="Asset not found")

    static_dir = bsm_frontend.get_static_dir()
    index_path = os.path.join(static_dir, "index.html")

    if os.path.exists(index_path):
        root_path = request.scope.get("root_path", "")
        if not root_path:
            return FileResponse(index_path)

        # Dynamically rewrite absolute /app/ asset paths in the HTML
        # to include the reverse proxy's root_path.
        with open(index_path, "r", encoding="utf-8") as f:
            content = f.read()

        import html

        # Add a trailing slash for the base url injection so relative paths work
        base_app_url = str(request.url_for("serve_spa"))
        if not base_app_url.endswith("/"):
            base_app_url += "/"

        # Escape the URL to prevent XSS from malicious Host or Ingress-Path headers
        safe_url = html.escape(base_app_url)

        # Inject the <base href> tag into the <head> to fix all relative assets.
        # Use proper \n (newline), not \\n (literal backslash + n).
        content = content.replace("<head>", f'<head>\n    <base href="{safe_url}" />')

        from fastapi.responses import HTMLResponse

        return HTMLResponse(content=content)

    raise HTTPException(status_code=404, detail="Frontend not found.")
