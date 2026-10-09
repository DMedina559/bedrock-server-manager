import logging

from ..context import AppContext
from ..error import BSMError, FileOperationError, MissingArgumentError
from ..plugins.api_bridge import api_method
from ..plugins.event_trigger import trigger_event
from .models.allowlist import (
    AddToAllowlistRequest,
    AddToAllowlistResponse,
    GetAllowlistRequest,
    GetAllowlistResponse,
    RemoveFromAllowlistRequest,
    RemoveFromAllowlistResponse,
)

logger = logging.getLogger(__name__)


@api_method("add_to_allowlist")
@trigger_event(
    before="before_allowlist_change",
    after="after_allowlist_change",
    identity_keys=("server_name",),
)
async def add_to_allowlist(
    request: AddToAllowlistRequest, *, app_context: AppContext
) -> AddToAllowlistResponse:
    """Adds a list of players to the server's allowlist.

    Accepts AddToAllowlistRequest and returns AddToAllowlistResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    server_name = request.server_name
    new_players_data = request.model_dump(mode="python")["new_players_data"]
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    if not isinstance(new_players_data, list):
        raise BSMError("Invalid input: new_players_data must be a list.")
    logger.info(
        f"API: Adding {len(new_players_data)} player(s) to allowlist for '{server_name}'."
    )
    try:
        server = app_context.get_server(server_name)
        added_count = await server.add_to_allowlist(new_players_data)
        return AddToAllowlistResponse.model_validate(
            {
                "status": "success",
                "message": f"Successfully added {added_count} new players to the allowlist.",
                "added_count": added_count,
            }
        )
    except (FileOperationError, TypeError) as e:
        logger.error(
            f"API: Failed to update allowlist for '{server_name}': {e}", exc_info=True
        )
        raise
    except Exception as e:
        logger.error(
            f"API: Unexpected error updating allowlist for '{server_name}': {e}",
            exc_info=True,
        )
        raise


@api_method("get_allowlist")
async def get_allowlist(
    request: GetAllowlistRequest, *, app_context: AppContext
) -> GetAllowlistResponse:
    """Retrieves the current allowlist for a given server.

    Accepts GetAllowlistRequest and returns GetAllowlistResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    server_name = request.server_name
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    try:
        server = app_context.get_server(server_name)
        players = await server.get_allowlist()
        return GetAllowlistResponse.model_validate(
            {"status": "success", "players": players}
        )
    except BSMError as e:
        logger.error(
            f"API: Failed to access allowlist for '{server_name}': {e}", exc_info=True
        )
        raise
    except Exception as e:
        logger.error(
            f"API: Unexpected error reading allowlist for '{server_name}': {e}",
            exc_info=True,
        )
        raise


@api_method("remove_from_allowlist")
@trigger_event(
    before="before_allowlist_change",
    after="after_allowlist_change",
    identity_keys=("server_name",),
)
async def remove_from_allowlist(
    request: RemoveFromAllowlistRequest, *, app_context: AppContext
) -> RemoveFromAllowlistResponse:
    """Removes a list of players from the server's allowlist.

    Accepts RemoveFromAllowlistRequest and returns RemoveFromAllowlistResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    server_name = request.server_name
    player_names = request.player_names
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    try:
        if not player_names:
            return RemoveFromAllowlistResponse.model_validate(
                {
                    "status": "success",
                    "message": "No players specified for removal.",
                    "details": {"removed": [], "not_found": []},
                }
            )
        server = app_context.get_server(server_name)
        removed_players, not_found_players = ([], [])
        for player in player_names:
            if await server.remove_from_allowlist(player):
                removed_players.append(player)
            else:
                not_found_players.append(player)
        return RemoveFromAllowlistResponse.model_validate(
            {
                "status": "success",
                "message": "Allowlist update process completed.",
                "details": {"removed": removed_players, "not_found": not_found_players},
            }
        )
    except BSMError as e:
        logger.error(
            f"API: Failed to remove players from allowlist for '{server_name}': {e}",
            exc_info=True,
        )
        raise
    except Exception as e:
        logger.error(
            f"API: Unexpected error removing players for '{server_name}': {e}",
            exc_info=True,
        )
        raise
