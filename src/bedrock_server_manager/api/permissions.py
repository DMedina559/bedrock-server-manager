import logging
from typing import Any, Dict, List

from ..context import AppContext
from ..error import AppFileNotFoundError, BSMError, InvalidServerNameError
from ..logging import log_operation_error
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
        await server.permissions.set_player_permission(xuid, permission, player_name)
        return SetPermissionsResponse.model_validate(
            {
                "status": "success",
                "message": f"Permission for XUID '{xuid}' set to '{permission.lower()}'.",
            }
        )
    except BSMError as e:
        log_operation_error(
            logger,
            "Failed to configure permission for '%s': %s",
            server_name,
            e,
            error=e,
        )
        raise
    except Exception as e:
        log_operation_error(
            logger,
            "Unexpected error configuring permission for '%s': %s",
            server_name,
            e,
            error=e,
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
        players_response = await player_api.get_all_known_players(
            request=GetAllKnownPlayersRequest(), app_context=app_context
        )
        all_known_players = players_response.players
        permissions: List[Dict[str, Any]] = []
        try:
            storage = app_context.storage
            permissions = await server.permissions.get_formatted_permissions(storage)
        except AppFileNotFoundError:
            permissions = []
        existing_xuids = {p.get("xuid") for p in permissions if p.get("xuid")}
        for player in all_known_players:
            xuid = player.xuid
            if xuid and xuid not in existing_xuids:
                permissions.append(
                    {
                        "xuid": xuid,
                        "name": player.name,
                        "permission_level": "member",
                    }
                )
                existing_xuids.add(xuid)
        permissions.sort(key=lambda x: str(x.get("name", "")).lower())
        return GetPermissionsResponse.model_validate(
            {"status": "success", "permissions": permissions}
        )
    except BSMError as e:
        log_operation_error(
            logger, "Failed to get permissions for '%s': %s", server_name, e, error=e
        )
        raise
    except Exception as e:
        log_operation_error(
            logger,
            "Unexpected error getting permissions for '%s': %s",
            server_name,
            e,
            error=e,
        )
        raise
