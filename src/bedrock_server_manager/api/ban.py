import logging

from ..context import AppContext
from ..error import BSMError, UserInputError
from ..plugins.api_bridge import api_method
from ..plugins.api_contract import validate_contract
from ..plugins.event_trigger import trigger_event
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
    """Adds a player to the server ban list.

    Accepts AddServerBanRequest and returns AddServerBanResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
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
    if not ban_res.success:
        raise BSMError(ban_res.message)
    return AddServerBanResponse.model_validate(
        {"status": "success", "message": ban_res.message}
    )


@validate_contract
@trigger_event(
    before="before_remove_server_ban",
    after="after_remove_server_ban",
    identity_keys=("server_name", "xuid"),
)
async def remove_server_ban(
    request: RemoveServerBanRequest, *, app_context: AppContext
) -> RemoveServerBanResponse:
    """Removes a player from the server ban list.

    Accepts RemoveServerBanRequest and returns RemoveServerBanResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
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
    if not ban_res.success:
        raise BSMError(ban_res.message)
    return RemoveServerBanResponse.model_validate(
        {"status": "success", "message": ban_res.message}
    )


@api_method("get_server_bans")
async def get_server_bans(
    request: GetServerBansRequest, *, app_context: AppContext
) -> GetServerBansResponse:
    """Retrieves all bans for a specific server.

    Accepts GetServerBansRequest and returns GetServerBansResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    server_name = request.server_name
    if not server_name:
        raise UserInputError("server_name is required.")
    if not getattr(app_context, "_storage", None):
        raise BSMError("Database is not initialized.")
    ban_res = await app_context.server_service.get_server_bans(server_name=server_name)
    if not ban_res.success:
        raise BSMError(ban_res.message)
    return GetServerBansResponse.model_validate(
        {"status": "success", "bans": [ban.model_dump() for ban in ban_res.bans or []]}
    )
