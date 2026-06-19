import os

import bsm_frontend
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse

router = APIRouter(prefix="", tags=["SPA"])


@router.get("/")
async def root():
    """Redirects root to /app"""
    return RedirectResponse(url="/app")


@router.get("/site.webmanifest")
async def serve_webmanifest():
    """Serves the site.webmanifest from the static directory."""
    static_dir = bsm_frontend.get_static_dir()
    manifest_path = os.path.join(static_dir, "site.webmanifest")

    if os.path.exists(manifest_path):
        return FileResponse(manifest_path)

    raise HTTPException(status_code=404, detail="Manifest not found.")


@router.get("/app")
@router.get("/app/{full_path:path}")
async def serve_spa(request: Request, full_path: str = ""):
    """Serves the SPA index.html for all /app routes, excluding assets."""

    if full_path.startswith("assets/"):
        raise HTTPException(status_code=404, detail="Asset not found")

    static_dir = bsm_frontend.get_static_dir()
    index_path = os.path.join(static_dir, "index.html")

    if os.path.exists(index_path):
        return FileResponse(index_path)

    raise HTTPException(status_code=404, detail="Frontend not found.")
