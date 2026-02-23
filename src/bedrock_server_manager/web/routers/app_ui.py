import os

from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse

router = APIRouter(prefix="", tags=["app_ui"])


@router.get("/app", include_in_schema=False)
async def redirect_app_root():
    """Redirects /app to /app/ so the SPA is served correctly."""
    return RedirectResponse(url="/app/")


@router.get("/v2", include_in_schema=False)
@router.get("/v2/{full_path:path}", include_in_schema=False)
async def redirect_v2(full_path: str = ""):
    """Redirects /v2 and /v2/... to /app/..."""
    target = "/app/"
    if full_path:
        target += full_path
    return RedirectResponse(url=target)


@router.get("/app/{full_path:path}")
async def serve_spa(full_path: str):
    if full_path.startswith("assets/"):
        return JSONResponse(content={"detail": "Asset not found"}, status_code=404)

    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # The build output is still in static/v2
    index_path = os.path.join(base_path, "static", "v2", "index.html")

    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "App UI not built or installed."}
