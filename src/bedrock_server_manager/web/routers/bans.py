from fastapi import APIRouter, Depends

from bedrock_server_manager.api.models import (
    AddServerBanRequest,
    AddServerBanResponse,
    GetServerBansRequest,
    GetServerBansResponse,
    RemoveServerBanRequest,
    RemoveServerBanResponse,
)

from ...api.ban import add_server_ban
from ...api.ban import get_server_bans as get_server_bans_api
from ...api.ban import remove_server_ban
from ...context import AppContext
from ..deps import get_admin_user, get_app_context, validate_server_exists
from ..schemas.ban import BanAddRequest, BanRemoveRequest

router = APIRouter(
    prefix="/api/server/{server_name}/bans",
    tags=["Server Bans", "Player Management"],
    dependencies=[Depends(get_admin_user), Depends(validate_server_exists)],
)


@router.get(
    "/get", operation_id="get_server_bans", response_model=GetServerBansResponse
)
async def get_server_bans(
    server_name: str = Depends(validate_server_exists),
    app_context: AppContext = Depends(get_app_context),
) -> GetServerBansResponse:
    """Get all bans for a specific server."""
    result = await get_server_bans_api(
        request=GetServerBansRequest(server_name=server_name),
        app_context=app_context,
    )
    return result


@router.post("/add", operation_id="add_server_ban", response_model=AddServerBanResponse)
async def post_add_server_ban(
    payload: BanAddRequest,
    server_name: str = Depends(validate_server_exists),
    app_context: AppContext = Depends(get_app_context),
) -> AddServerBanResponse:
    """Add a player to the server ban list."""
    result = await add_server_ban(
        request=AddServerBanRequest(
            server_name=server_name,
            player_name=payload.player_name,
            xuid=payload.xuid,
            reason=payload.reason,
        ),
        app_context=app_context,
    )
    return result


@router.delete(
    "/remove", operation_id="remove_server_ban", response_model=RemoveServerBanResponse
)
async def delete_remove_server_ban(
    payload: BanRemoveRequest,
    server_name: str = Depends(validate_server_exists),
    app_context: AppContext = Depends(get_app_context),
) -> RemoveServerBanResponse:
    """Remove a player from the server ban list."""
    result = await remove_server_ban(
        request=RemoveServerBanRequest(server_name=server_name, xuid=payload.xuid),
        app_context=app_context,
    )
    return result
