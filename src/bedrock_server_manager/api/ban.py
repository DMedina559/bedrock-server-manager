import logging

from ..context import AppContext
from ..error import BSMError, UserInputError
from ..events import trigger_event
from ..plugins.api_bridge import api_method
from .models.ban import (
    AddServerBanRequest,
    AddServerBanResponse,
    GetServerBansRequest,
    GetServerBansResponse,
    RemoveServerBanRequest,
    RemoveServerBanResponse,
)

logger = logging.getLogger(__name__)


@api_method("add_server_ban")
@trigger_event(
    before="before_add_server_ban",
    after="after_add_server_ban",
    identity_keys=("server_name", "xuid"),
)
async def add_server_ban(
    request: AddServerBanRequest, *, app_context: AppContext
) -> AddServerBanResponse:
    """Adds a player to the server ban list."""
    server_name = request.server_name
    player_name = request.player_name
    xuid = request.xuid
    reason = request.reason
    if not server_name or not player_name or (not xuid):
        raise UserInputError("server_name, player_name, and xuid are required.")
    if not getattr(app_context, "_storage", None):
        raise BSMError("Database is not initialized.")
    logger.info(
        "Adding ban for player '%s' (%s) on server '%s'.",
        player_name,
        xuid,
        server_name,
    )
    ban_res = await app_context.server_service.add_server_ban(
        server_name=server_name, player_name=player_name, xuid=xuid, reason=reason
    )
    return AddServerBanResponse(
        server_name=server_name, status="success", message=ban_res.message
    )


@api_method("remove_server_ban")
@trigger_event(
    before="before_remove_server_ban",
    after="after_remove_server_ban",
    identity_keys=("server_name", "xuid"),
)
async def remove_server_ban(
    request: RemoveServerBanRequest, *, app_context: AppContext
) -> RemoveServerBanResponse:
    """Remove a player from the server ban list."""
    server_name = request.server_name
    xuid = request.xuid
    if not server_name or not xuid:
        raise UserInputError("server_name and xuid are required.")
    if not getattr(app_context, "_storage", None):
        raise BSMError("Database is not initialized.")
    logger.info("Removing ban for XUID '%s' on server '%s'.", xuid, server_name)
    ban_res = await app_context.server_service.remove_server_ban(
        server_name=server_name, xuid=xuid
    )
    return RemoveServerBanResponse(
        server_name=server_name, status="success", message=ban_res.message
    )


@api_method("get_server_bans")
async def get_server_bans(
    request: GetServerBansRequest, *, app_context: AppContext
) -> GetServerBansResponse:
    """Return all bans for a specific server."""
    server_name = request.server_name
    if not getattr(app_context, "_storage", None):
        raise BSMError("Database is not initialized.")
    ban_res = await app_context.server_service.get_server_bans(server_name=server_name)
    return GetServerBansResponse.model_validate(
        {"status": "success", "bans": [ban.model_dump() for ban in ban_res]}
    )
