import logging
from typing import Any, Dict, Optional

from ..context import AppContext
from ..error import UserInputError
from ..plugins.api_bridge import api_method
from ..plugins.event_trigger import trigger_event

logger = logging.getLogger(__name__)


@api_method("add_server_ban_api")
@trigger_event(
    before="before_add_server_ban",
    after="after_add_server_ban",
    identity_keys=("server_name", "xuid"),
)
async def add_server_ban_api(
    app_context: AppContext,
    server_name: str,
    player_name: str,
    xuid: str,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    """Adds a player to the server ban list."""
    if not server_name or not player_name or not xuid:
        raise UserInputError("server_name, player_name, and xuid are required.")

    logger.info(
        f"API: Adding ban for player '{player_name}' ({xuid}) on server '{server_name}'."
    )
    ban_res = await app_context.server_service.add_server_ban(
        server_name=server_name, player_name=player_name, xuid=xuid, reason=reason
    )
    return {
        "status": "success" if ban_res.success else "error",
        "message": ban_res.message,
    }


@trigger_event(
    before="before_remove_server_ban",
    after="after_remove_server_ban",
    identity_keys=("server_name", "xuid"),
)
async def remove_server_ban_api(
    app_context: AppContext, server_name: str, xuid: str
) -> Dict[str, Any]:
    """Removes a player from the server ban list."""
    if not server_name or not xuid:
        raise UserInputError("server_name and xuid are required.")

    logger.info(f"API: Removing ban for XUID '{xuid}' on server '{server_name}'.")
    ban_res = await app_context.server_service.remove_server_ban(
        server_name=server_name, xuid=xuid
    )
    return {
        "status": "success" if ban_res.success else "error",
        "message": ban_res.message,
    }


@api_method("get_server_bans_api")
async def get_server_bans_api(
    app_context: AppContext, server_name: str
) -> Dict[str, Any]:
    """Retrieves all bans for a specific server."""
    if not server_name:
        raise UserInputError("server_name is required.")

    ban_res = await app_context.server_service.get_server_bans(server_name=server_name)
    if not ban_res.success:
        return {"status": "error", "message": ban_res.message}
    return {
        "status": "success",
        "bans": [ban.model_dump() for ban in (ban_res.bans or [])],
    }
