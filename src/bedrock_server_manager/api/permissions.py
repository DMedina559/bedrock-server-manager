import logging
from typing import Any, Dict, List, Optional

from ..context import AppContext
from ..error import AppFileNotFoundError, BSMError, InvalidServerNameError
from ..plugins.api_bridge import api_method
from ..plugins.event_trigger import trigger_app_event
from . import player as player_api

logger = logging.getLogger(__name__)


@api_method("set_permissions")
@trigger_app_event(before="before_permission_change", after="after_permission_change")
def set_permissions(
    server_name: str,
    xuid: str,
    player_name: Optional[str],
    permission: str,
    app_context: AppContext,
) -> Dict[str, str]:
    """Sets a player's permission level for a given server.

    Args:
        server_name (str): The name of the server.
        xuid (str): The XUID of the player.
        player_name (Optional[str]): The name of the player.
        permission (str): The permission level to grant.
        app_context (AppContext): The application context.

    Returns:
        Dict[str, str]: A dictionary with the status and result message.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    try:
        server = app_context.get_server(server_name)
        server.set_player_permission(xuid, permission, player_name)

        return {
            "status": "success",
            "message": f"Permission for XUID '{xuid}' set to '{permission.lower()}'.",
        }

    except BSMError as e:
        logger.error(
            f"API: Failed to configure permission for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Failed to configure permission: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error configuring permission for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Unexpected error: {e}"}


@api_method("get_permissions")
def get_permissions(  # noqa: C901
    server_name: str, app_context: AppContext
) -> Dict[str, Any]:
    """Retrieves the permissions configuration for a server, formatted with player names.

    Args:
        server_name (str): The name of the server.
        app_context (AppContext): The application context.

    Returns:
        Dict[str, Any]: A dictionary containing a list of permission objects.
    """
    if not server_name:
        return {"status": "error", "message": "Server name cannot be empty."}

    try:
        server = app_context.get_server(server_name)
        player_name_map: Dict[str, str] = {}
        all_known_players: List[Dict[str, Any]] = []

        players_response = player_api.get_all_known_players_api(app_context=app_context)
        if players_response.get("status") == "success":
            all_known_players = players_response.get("players", []) or []
            for p_data in all_known_players:
                if p_data.get("xuid") and p_data.get("name"):
                    player_name_map[str(p_data["xuid"])] = str(p_data["name"])

        permissions: List[Dict[str, Any]] = []
        try:
            permissions = server.get_formatted_permissions(player_name_map)
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

        permissions.sort(key=lambda x: x.get("name", "").lower())

        return {"status": "success", "permissions": permissions}
    except BSMError as e:
        logger.error(
            f"API: Failed to get permissions for '{server_name}': {e}", exc_info=True
        )
        return {"status": "error", "message": f"Failed to get permissions: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error getting permissions for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Unexpected error: {e}"}
