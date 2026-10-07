# bedrock_server_manager/api/player.py
"""Provides API functions for managing the central player database.

This module offers an interface to interact with the application's central
player database, typically stored in the database. It leverages the
application context to perform operations such as:

- Manually adding or updating player entries (gamertag and XUID) via
  :func:`~.add_players_manually`.
- Retrieving all known player entries from the database using
  :func:`~.get_all_known_players`.
- Discovering players by scanning server logs and updating the database via
  :func:`~.scan_and_update_player_db`.

These functions are exposed to the plugin system and provide a structured way
to manage player data globally across all server instances.
"""

import logging

from ..context import AppContext
from ..core.player import (
    discover_and_store_players,
    get_known_players,
    parse_player_string,
    save_player_data,
)
from ..error import BSMError, UserInputError
from ..plugins.api_bridge import api_method
from ..plugins.event_trigger import trigger_event
from .models.player import (
    AddPlayersManuallyRequest,
    AddPlayersManuallyResponse,
    GetAllKnownPlayersRequest,
    GetAllKnownPlayersResponse,
    ScanAndUpdatePlayerDbRequest,
    ScanAndUpdatePlayerDbResponse,
)

logger = logging.getLogger(__name__)


@api_method("add_players_manually")
@trigger_event(before="before_players_add", after="after_players_add", identity_keys=())
async def add_players_manually(
    request: AddPlayersManuallyRequest, *, app_context: AppContext
) -> AddPlayersManuallyResponse:
    """Adds or updates player data in the database.

    Accepts AddPlayersManuallyRequest and returns AddPlayersManuallyResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    player_strings = request.player_strings
    logger.info(f"API: Adding players manually: {player_strings}")
    storage = app_context.storage
    if storage is None:
        raise BSMError("Storage is not initialized.")
    if (
        not player_strings
        or not isinstance(player_strings, list)
        or (not all((isinstance(s, str) for s in player_strings)))
    ):
        raise BSMError("Input must be a non-empty list of player strings.")
    try:
        combined_input = ",".join(player_strings)
        players_data = parse_player_string(combined_input)
        if players_data:
            await save_player_data(storage, players_data)
        return AddPlayersManuallyResponse.model_validate(
            {
                "status": "success",
                "message": f"{len(player_strings)} player entries processed and saved/updated.",
                "count": len(player_strings),
            }
        )
    except UserInputError:
        raise
    except BSMError:
        raise
    except Exception as e:
        logger.error(f"API: Unexpected error adding players: {e}", exc_info=True)
        raise


@api_method("get_all_known_players")
async def get_all_known_players(
    request: GetAllKnownPlayersRequest, *, app_context: AppContext
) -> GetAllKnownPlayersResponse:
    """Retrieves all player data from the database.

    Accepts GetAllKnownPlayersRequest and returns GetAllKnownPlayersResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    logger.info("API: Request to get all known players.")
    storage = app_context.storage
    if storage is None:
        raise BSMError("Storage is not initialized.")
    try:
        players = await get_known_players(storage)
        return GetAllKnownPlayersResponse.model_validate(
            {"status": "success", "players": players}
        )
    except Exception as e:
        logger.error(f"API: Unexpected error getting players: {e}", exc_info=True)
        raise


@api_method("scan_and_update_player_db")
@trigger_event(
    before="before_player_db_scan", after="after_player_db_scan", identity_keys=()
)
async def scan_and_update_player_db(
    request: ScanAndUpdatePlayerDbRequest, *, app_context: AppContext
) -> ScanAndUpdatePlayerDbResponse:
    """Scans all server logs to discover and save player data.

    Accepts ScanAndUpdatePlayerDbRequest and returns ScanAndUpdatePlayerDbResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    logger.info("API: Request to scan all server logs and update player DB.")
    storage = app_context.storage
    if storage is None:
        raise BSMError("Storage is not initialized.")
    try:
        base_dir = app_context.settings.get("paths.servers", "")
        scan_result = await discover_and_store_players(base_dir, app_context)
        message = f"Player DB update complete. Entries found in logs: {scan_result['total_entries_in_logs']}. Unique players submitted: {scan_result['unique_players_submitted_for_saving']}. Actually saved/updated: {scan_result['actually_saved_or_updated_in_db']}."
        if scan_result["scan_errors"]:
            message += f" Scan errors encountered for: {scan_result['scan_errors']}"
        return ScanAndUpdatePlayerDbResponse.model_validate(
            {"status": "success", "message": message, "details": scan_result}
        )
    except BSMError:
        raise
    except Exception as e:
        logger.error(f"API: Unexpected error scanning for players: {e}", exc_info=True)
        raise
