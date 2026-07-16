import logging
import os
from typing import Any, Dict, List

from ..context import AppContext
from ..db.models import Player
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


def save_player_data(db_session_manager, players_data: List[Dict[str, str]]) -> int:
    """Saves or updates player data in the database."""
    if not isinstance(players_data, list):
        raise UserInputError("players_data must be a list.")
    for p_data in players_data:
        if not (
            isinstance(p_data, dict)
            and "name" in p_data
            and "xuid" in p_data
            and isinstance(p_data["name"], str)
            and p_data["name"]
            and isinstance(p_data["xuid"], str)
            and p_data["xuid"]
        ):
            raise UserInputError(f"Invalid player entry format: {p_data}")

    with db_session_manager as db:
        try:
            updated_count = 0
            added_count = 0
            for player_to_add in players_data:
                xuid = player_to_add["xuid"]
                player = db.query(Player).filter_by(xuid=xuid).first()
                if player:
                    if (
                        player.player_name != player_to_add["name"]
                        or player.xuid != player_to_add["xuid"]
                    ):
                        player.player_name = player_to_add["name"]
                        player.xuid = player_to_add["xuid"]
                        updated_count += 1
                else:
                    player = Player(
                        player_name=player_to_add["name"],
                        xuid=player_to_add["xuid"],
                    )
                    db.add(player)
                    added_count += 1

            if updated_count > 0 or added_count > 0:
                db.commit()
                logger.info(
                    f"Saved/Updated players. Added: {added_count}, Updated: {updated_count}."
                )
                return added_count + updated_count

            logger.debug("No new or updated player data to save.")
            return 0
        except Exception as e:
            db.rollback()
            raise e


def get_known_players(db_session_manager) -> List[Dict[str, str]]:
    """Retrieves all known players from the database."""
    with db_session_manager as db:
        players = db.query(Player).all()
        return [{"name": player.player_name, "xuid": player.xuid} for player in players]


def discover_and_store_players(  # noqa: C901
    base_dir: str, app_context: AppContext
) -> Dict[str, Any]:
    """Scans all server logs for player data and updates the central player database."""
    if not base_dir or not os.path.isdir(base_dir):
        raise AppFileNotFoundError(str(base_dir), "Server base directory")

    all_discovered_from_logs: List[Dict[str, str]] = []
    scan_errors_details: List[Dict[str, str]] = []

    logger.info(f"Starting discovery of players from all server logs in '{base_dir}'.")

    for server_name_candidate in os.listdir(base_dir):
        potential_server_path = os.path.join(base_dir, server_name_candidate)
        if not os.path.isdir(potential_server_path):
            continue

        logger.debug(f"Processing potential server '{server_name_candidate}'.")
        try:
            # Instantiate a BedrockServer to use its encapsulated logic.
            server_instance = app_context.get_server(server_name_candidate)

            # Validate it's a real server before trying to scan its logs.
            if not server_instance.is_installed():
                logger.debug(
                    f"'{server_name_candidate}' is not a valid Bedrock server installation. Skipping log scan."
                )
                continue

            # Use the instance's own method to scan its log file.
            players_in_log = server_instance.scan_log_for_players()
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
        # Consolidate all found players into a unique set by XUID.
        unique_players_to_save_map = {p["xuid"]: p for p in all_discovered_from_logs}
        unique_players_to_save_list = list(unique_players_to_save_map.values())
        try:
            # Save all unique players to the central database.
            saved_count = save_player_data(
                app_context.db.session_manager(), unique_players_to_save_list
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
