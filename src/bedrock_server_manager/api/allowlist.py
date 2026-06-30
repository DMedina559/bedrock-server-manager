import logging
from typing import Any, Dict, List

from ..context import AppContext
from ..error import BSMError, FileOperationError, MissingArgumentError
from ..plugins.api_bridge import api_method
from ..plugins.event_trigger import trigger_app_event

logger = logging.getLogger(__name__)


@api_method("add_to_allowlist")
@trigger_app_event(before="before_allowlist_change", after="after_allowlist_change")
def add_to_allowlist(
    server_name: str,
    new_players_data: List[Dict[str, Any]],
    app_context: AppContext,
) -> Dict[str, Any]:
    """Adds a list of players to the server's allowlist.

    Args:
        server_name (str): The name of the server.
        new_players_data (List[Dict[str, Any]]): List of player dictionaries (with 'name' and 'xuid').
        app_context (AppContext): The application context.

    Returns:
        Dict[str, Any]: Status dictionary containing success or error message.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    if not isinstance(new_players_data, list):
        return {
            "status": "error",
            "message": "Invalid input: new_players_data must be a list.",
        }

    logger.info(
        f"API: Adding {len(new_players_data)} player(s) to allowlist for '{server_name}'."
    )
    try:
        server = app_context.get_server(server_name)
        added_count = server.add_to_allowlist(new_players_data)

        return {
            "status": "success",
            "message": f"Successfully added {added_count} new players to the allowlist.",
            "added_count": added_count,
        }

    except (FileOperationError, TypeError) as e:
        logger.error(
            f"API: Failed to update allowlist for '{server_name}': {e}", exc_info=True
        )
        return {"status": "error", "message": f"Failed to update allowlist: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error updating allowlist for '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Unexpected error updating allowlist: {e}",
        }


@api_method("get_allowlist")
def get_allowlist(server_name: str, app_context: AppContext) -> Dict[str, Any]:
    """Retrieves the current allowlist for a given server.

    Args:
        server_name (str): The name of the server.
        app_context (AppContext): The application context.

    Returns:
        Dict[str, Any]: A dictionary containing the list of players on the allowlist.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")

    try:
        server = app_context.get_server(server_name)
        players = server.get_allowlist()
        return {"status": "success", "players": players}
    except BSMError as e:
        logger.error(
            f"API: Failed to access allowlist for '{server_name}': {e}", exc_info=True
        )
        return {"status": "error", "message": f"Failed to access allowlist: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error reading allowlist for '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Unexpected error reading allowlist: {e}",
        }


@api_method("remove_from_allowlist")
@trigger_app_event(before="before_allowlist_change", after="after_allowlist_change")
def remove_from_allowlist(
    server_name: str,
    player_names: List[str],
    app_context: AppContext,
) -> Dict[str, Any]:
    """Removes a list of players from the server's allowlist.

    Args:
        server_name (str): The name of the server.
        player_names (List[str]): List of player names to remove.
        app_context (AppContext): The application context.

    Returns:
        Dict[str, Any]: Status dictionary containing success or error message,
        and details of removed vs not_found players.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")

    try:
        if not player_names:
            return {
                "status": "success",
                "message": "No players specified for removal.",
                "details": {"removed": [], "not_found": []},
            }

        server = app_context.get_server(server_name)
        removed_players, not_found_players = [], []

        for player in player_names:
            if server.remove_from_allowlist(player):
                removed_players.append(player)
            else:
                not_found_players.append(player)

        return {
            "status": "success",
            "message": "Allowlist update process completed.",
            "details": {"removed": removed_players, "not_found": not_found_players},
        }

    except BSMError as e:
        logger.error(
            f"API: Failed to remove players from allowlist for '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Failed to process allowlist removal: {e}",
        }
    except Exception as e:
        logger.error(
            f"API: Unexpected error removing players for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Unexpected error: {e}"}
