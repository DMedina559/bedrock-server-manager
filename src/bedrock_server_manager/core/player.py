import logging
import os
from typing import Any, Dict, List

from ..context import AppContext
from ..error import (
    AppFileNotFoundError,
    FileOperationError,
    UserInputError,
)

logger = logging.getLogger(__name__)


def parse_player_string(player_string: str) -> List[Dict[str, str]]:
    """Parses a comma-separated string of 'player_name:xuid' pairs."""
    if not player_string or not isinstance(player_string, str):
        return []
    logger.debug(f"Parsing player argument string: '{player_string}'")
    player_list: List[Dict[str, str]] = []
    player_pairs = [pair.strip() for pair in player_string.split(",") if pair.strip()]
    for pair in player_pairs:
        player_data = pair.split(":", 1)
        if len(player_data) != 2:
            raise UserInputError(
                f"Invalid player data format: '{pair}'. Expected 'name:xuid'."
            )
        player_name, player_id = player_data[0].strip(), player_data[1].strip()
        if not player_name or not player_id:
            raise UserInputError(f"Name and XUID cannot be empty in '{pair}'.")
        player_list.append({"name": player_name, "xuid": player_id})
    return player_list


async def save_player_data(storage: Any, players_data: List[Dict[str, str]]) -> int:
    """Saves or updates player data in the database asynchronously via Storage."""
    res = await storage.save_players(players_data)
    return int(res)


async def get_known_players(storage: Any) -> List[Dict[str, str]]:
    """Retrieves all known players from the database asynchronously via Storage."""
    res = await storage.get_all_players()
    return list(res)


async def discover_and_store_players(  # noqa: C901
    base_dir: str, app_context: AppContext
) -> Dict[str, Any]:
    """Scans all server logs for player data and updates the central player database asynchronously."""
    import aiofiles.os
    import aiofiles.ospath

    if not base_dir or not await aiofiles.ospath.isdir(base_dir):
        raise AppFileNotFoundError(str(base_dir), "Server base directory")

    all_discovered_from_logs: List[Dict[str, str]] = []
    scan_errors_details: List[Dict[str, str]] = []

    logger.info(f"Starting discovery of players from all server logs in '{base_dir}'.")

    for server_name_candidate in os.listdir(base_dir):
        potential_server_path = os.path.join(base_dir, server_name_candidate)
        if not await aiofiles.ospath.isdir(potential_server_path):
            continue

        logger.debug(f"Processing potential server '{server_name_candidate}'.")
        try:
            server_instance = app_context.get_server(server_name_candidate)
            is_installed = await server_instance.is_installed()

            if not is_installed:
                logger.debug(
                    f"'{server_name_candidate}' is not a valid Bedrock server installation. Skipping log scan."
                )
                continue

            players_in_log = await server_instance.player_tracker.scan_log_for_players()

            if players_in_log:
                all_discovered_from_logs.extend(players_in_log)
                logger.debug(
                    f"Found {len(players_in_log)} players in log for server '{server_name_candidate}'."
                )

        except FileOperationError as e:
            logger.warning(
                f"Error scanning log for server '{server_name_candidate}': {e}"
            )
            scan_errors_details.append(
                {"server": server_name_candidate, "error": str(e)}
            )
        except Exception as e_instantiate:
            logger.error(
                f"Error processing server '{server_name_candidate}' for player discovery: {e_instantiate}",
                exc_info=True,
            )
            scan_errors_details.append(
                {
                    "server": server_name_candidate,
                    "error": f"Unexpected error: {str(e_instantiate)}",
                }
            )

    saved_count = 0
    unique_players_to_save_map = {}
    if all_discovered_from_logs:
        unique_players_to_save_map = {p["xuid"]: p for p in all_discovered_from_logs}
        unique_players_to_save_list = list(unique_players_to_save_map.values())
        try:
            saved_count = await save_player_data(
                app_context.storage, unique_players_to_save_list
            )
        except (FileOperationError, Exception) as e_save:
            logger.error(
                f"Critical error saving player data to global DB: {e_save}",
                exc_info=True,
            )
            scan_errors_details.append(
                {
                    "server": "GLOBAL_PLAYER_DB",
                    "error": f"Save failed: {str(e_save)}",
                }
            )

    return {
        "total_entries_in_logs": len(all_discovered_from_logs),
        "unique_players_submitted_for_saving": len(unique_players_to_save_map),
        "actually_saved_or_updated_in_db": saved_count,
        "scan_errors": scan_errors_details,
    }
