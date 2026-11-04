from fastapi import APIRouter, Depends, Security

from ...api.ban import add_server_ban
from ...api.ban import get_server_bans as get_server_bans_api
from ...api.ban import remove_server_ban
from ...context import AppContext
from ...models import (
    AddServerBanRequest,
    AddServerBanResponse,
    BanAddRequest,
    BanRemoveRequest,
    GetServerBansRequest,
    GetServerBansResponse,
    RemoveServerBanRequest,
    RemoveServerBanResponse,
)
from ..access_policy import Permission
from ..deps import get_app_context, validate_server_exists
from ..deps.auth import require_permissions
from ..schemas import UserResponse

router = APIRouter(
    prefix="/api/server/{server_name}/bans",
    tags=["Server Access"],
)


@router.get(
    "/get", operation_id="get_server_bans", response_model=GetServerBansResponse
)
async def get_server_bans(
    user: UserResponse = Security(require_permissions, scopes=[Permission.BANS_READ]),
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
    user: UserResponse = Security(require_permissions, scopes=[Permission.BANS_MANAGE]),
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
    user: UserResponse = Security(require_permissions, scopes=[Permission.BANS_MANAGE]),
    server_name: str = Depends(validate_server_exists),
    app_context: AppContext = Depends(get_app_context),
) -> RemoveServerBanResponse:
    """Remove a player from the server ban list."""
    result = await remove_server_ban(
        request=RemoveServerBanRequest(server_name=server_name, xuid=payload.xuid),
        app_context=app_context,
    )
    return result
