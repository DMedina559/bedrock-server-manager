from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from ...api.ban import add_server_ban_api, get_server_bans_api, remove_server_ban_api
from ...context import AppContext
from ..auth_utils import get_admin_user
from ..dependencies import get_app_context, validate_server_exists
from ..schemas.ban import BanAddRequest, BanRemoveRequest

router = APIRouter(
    prefix="/api/server/{server_name}/bans",
    tags=["Server Bans", "Player Management"],
    dependencies=[Depends(get_admin_user), Depends(validate_server_exists)],
)


@router.get("/get")
def get_server_bans(
    server_name: str = Depends(validate_server_exists),
    app_context: AppContext = Depends(get_app_context),
) -> Dict[str, Any]:
    """Get all bans for a specific server."""
    result = get_server_bans_api(app_context=app_context, server_name=server_name)
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("message"))
    return dict(result)


@router.post("/add")
def post_add_server_ban(
    payload: BanAddRequest,
    server_name: str = Depends(validate_server_exists),
    app_context: AppContext = Depends(get_app_context),
) -> Dict[str, Any]:
    """Add a player to the server ban list."""
    result = add_server_ban_api(
        app_context=app_context,
        server_name=server_name,
        player_name=payload.player_name,
        xuid=payload.xuid,
        reason=payload.reason,
    )
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("message"))
    return dict(result)


@router.delete("/remove")
def delete_remove_server_ban(
    payload: BanRemoveRequest,
    server_name: str = Depends(validate_server_exists),
    app_context: AppContext = Depends(get_app_context),
) -> Dict[str, Any]:
    """Remove a player from the server ban list."""
    result = remove_server_ban_api(
        app_context=app_context, server_name=server_name, xuid=payload.xuid
    )
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("message"))
    return dict(result)
