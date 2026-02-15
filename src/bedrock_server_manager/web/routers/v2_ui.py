import os

from fastapi import APIRouter
from fastapi.responses import FileResponse, RedirectResponse

router = APIRouter(prefix="/v2", tags=["v2_ui"])


@router.get("", include_in_schema=False)
async def redirect_root():
    """Redirects /v2 to /v2/ so the SPA is served correctly."""
    return RedirectResponse(url="/v2/")


@router.get("/{full_path:path}")
async def serve_spa(full_path: str):
    if full_path.startswith("assets/"):
        return {"detail": "Asset not found"}, 404

    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    index_path = os.path.join(base_path, "static", "v2", "index.html")

    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "V2 UI not built or installed."}
