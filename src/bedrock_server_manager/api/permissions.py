import logging
from typing import Any, Dict, List

from ..context import AppContext
from ..error import AppFileNotFoundError, BSMError, InvalidServerNameError
from ..plugins.api_bridge import api_method
from ..plugins.event_trigger import trigger_event
from . import player as player_api
from .models.permissions import (
    GetPermissionsRequest,
    GetPermissionsResponse,
    SetPermissionsRequest,
    SetPermissionsResponse,
)
from .models.player import GetAllKnownPlayersRequest

logger = logging.getLogger(__name__)


@api_method("set_permissions")
@trigger_event(
    before="before_permission_change",
    after="after_permission_change",
    identity_keys=("server_name", "xuid"),
)
async def set_permissions(
    request: SetPermissionsRequest, *, app_context: AppContext
) -> SetPermissionsResponse:
    """Sets a player's permission level for a given server.

    Accepts SetPermissionsRequest and returns SetPermissionsResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    server_name = request.server_name
    xuid = request.xuid
    player_name = request.player_name
    permission = request.permission
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    try:
        server = app_context.get_server(server_name)
        await server.set_player_permission(xuid, permission, player_name)
        return SetPermissionsResponse.model_validate(
            {
                "status": "success",
                "message": f"Permission for XUID '{xuid}' set to '{permission.lower()}'.",
            }
        )
    except BSMError as e:
        logger.error(
            f"API: Failed to configure permission for '{server_name}': {e}",
            exc_info=True,
        )
        raise
    except Exception as e:
        logger.error(
            f"API: Unexpected error configuring permission for '{server_name}': {e}",
            exc_info=True,
        )
        raise


@api_method("get_permissions")
async def get_permissions(
    request: GetPermissionsRequest, *, app_context: AppContext
) -> GetPermissionsResponse:
    """Retrieves the permissions configuration for a server, formatted with player names.

    Accepts GetPermissionsRequest and returns GetPermissionsResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    server_name = request.server_name
    if not server_name:
        raise BSMError("Server name cannot be empty.")
    try:
        server = app_context.get_server(server_name)
        all_known_players: List[Dict[str, Any]] = []
        players_response = (
            await player_api.get_all_known_players(
                request=GetAllKnownPlayersRequest(), app_context=app_context
            )
        ).model_dump(mode="python")
        if players_response.get("status") == "success":
            all_known_players = players_response.get("players", []) or []
        permissions: List[Dict[str, Any]] = []
        try:
            storage = app_context.storage
            permissions = await server.get_formatted_permissions(storage)
        except AppFileNotFoundError:
            permissions = []
        existing_xuids = {p.get("xuid") for p in permissions if p.get("xuid")}
        for player in all_known_players:
            xuid = str(player.get("xuid"))
            if xuid and xuid not in existing_xuids:
                permissions.append(
                    {
                        "xuid": xuid,
                        "name": player.get("name", "Unknown"),
                        "permission_level": "member",
                    }
                )
                existing_xuids.add(xuid)
        permissions.sort(key=lambda x: str(x.get("name", "")).lower())
        return GetPermissionsResponse.model_validate(
            {"status": "success", "permissions": permissions}
        )
    except BSMError as e:
        logger.error(
            f"API: Failed to get permissions for '{server_name}': {e}", exc_info=True
        )
        raise
    except Exception as e:
        logger.error(
            f"API: Unexpected error getting permissions for '{server_name}': {e}",
            exc_info=True,
        )
        raise
