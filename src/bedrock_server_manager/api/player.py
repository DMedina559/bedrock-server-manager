# bedrock_server_manager/api/player.py
"""Provides API functions for managing the central player database.

This module offers an interface to interact with the application's central
player database, typically stored in ``players.json``. It leverages the
:class:`~bedrock_server_manager.core.manager.BedrockServerManager`
to perform operations such as:

- Manually adding or updating player entries (gamertag and XUID) via
  :func:`~.add_players_manually_api`.
- Retrieving all known player entries from the database using
  :func:`~.get_all_known_players_api`.
- Discovering players by scanning server logs and updating the database via
  :func:`~.scan_and_update_player_db_api`.

These functions are exposed to the plugin system and provide a structured way
to manage player data globally across all server instances.
"""

import logging
from typing import Dict, List, Any, Optional

# Plugin system imports to bridge API functionality.
from ..plugins import plugin_method

# Local application imports.
from ..error import (
    BSMError,
    UserInputError,
)
from ..plugins.event_trigger import trigger_plugin_event
from ..context import AppContext

logger = logging.getLogger(__name__)


@plugin_method("add_players_manually_api")
@trigger_plugin_event(before="before_players_add", after="after_players_add")
def add_players_manually_api(
    player_strings: List[str],
    app_context: AppContext,
) -> Dict[str, Any]:
    """Adds or updates player data in the database.

    This function takes a list of strings, each containing a player's
    gamertag and XUID, parses them, and saves the data to the
    player database. It uses
    :meth:`~bedrock_server_manager.core.manager.BedrockServerManager.parse_player_cli_argument`
    (after joining the list into a single comma-separated string) and then
    :meth:`~bedrock_server_manager.core.manager.BedrockServerManager.save_player_data`.
    Triggers ``before_players_add`` and ``after_players_add`` plugin events.

    Args:
        player_strings (List[str]): A list of strings. Each string should
            represent a single player in the format "gamertag:xuid"
            (e.g., ``"PlayerOne:1234567890123456"``).
            Example list: ``["PlayerOne:123...", "PlayerTwo:654..."]``.

    Returns:
        Dict[str, Any]: A dictionary with the operation result.
        On success: ``{"status": "success", "message": "<n> player entries processed...", "count": <n>}``
        On error (parsing or saving): ``{"status": "error", "message": "<error_message>"}``

    Raises:
        UserInputError: If any player string in `player_strings` is malformed
            (propagated from ``parse_player_cli_argument``).
        BSMError: If saving to the database fails.
    """
    logger.info(f"API: Adding players manually: {player_strings}")
    # --- Input Validation ---
    if (
        not player_strings
        or not isinstance(player_strings, list)
        or not all(isinstance(s, str) for s in player_strings)
    ):
        return {
            "status": "error",
            "message": "Input must be a non-empty list of player strings.",
        }

    try:
        combined_input = ",".join(player_strings)
        app_context.manager.parse_player_cli_argument(combined_input)

        return {
            "status": "success",
            "message": f"{len(player_strings)} player entries processed and saved/updated.",
            "count": len(player_strings),
        }

    except UserInputError as e:
        # Handle errors related to invalid player string formats.
        return {"status": "error", "message": f"Invalid player data: {str(e)}"}

    except BSMError as e:
        # Handle errors during the file-saving process.
        return {"status": "error", "message": f"Error saving player data: {str(e)}"}

    except Exception as e:
        # Handle any other unexpected errors.
        logger.error(f"API: Unexpected error adding players: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"An unexpected error occurred: {str(e)}",
        }


@plugin_method("get_all_known_players_api")
def get_all_known_players_api(app_context: AppContext) -> Dict[str, Any]:
    """Retrieves all player data from the database.

    Calls :meth:`~bedrock_server_manager.core.manager.BedrockServerManager.get_known_players`.

    Returns:
        Dict[str, Any]: A dictionary with the operation result.
        On success: ``{"status": "success", "players": List[PlayerDict]}``
        where each ``PlayerDict`` typically contains "name" and "xuid".
        Returns an empty list for `players` if the database is empty.
        On unexpected error: ``{"status": "error", "message": "<error_message>"}``.
    """
    logger.info("API: Request to get all known players.")
    try:
        players = app_context.manager.get_known_players()
        return {"status": "success", "players": players}
    except Exception as e:
        logger.error(f"API: Unexpected error getting players: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"An unexpected error occurred retrieving players: {str(e)}",
        }


@plugin_method("scan_and_update_player_db_api")
@trigger_plugin_event(before="before_player_db_scan", after="after_player_db_scan")
def scan_and_update_player_db_api(app_context: AppContext) -> Dict[str, Any]:
    """Scans all server logs to discover and save player data.

    This function iterates through the log files of all managed servers,
    extracts player connection information (gamertag and XUID), and updates
    the central player database with any new findings. It calls
    :meth:`~bedrock_server_manager.core.manager.BedrockServerManager.discover_and_store_players_from_all_server_logs`.
    Triggers ``before_player_db_scan`` and ``after_player_db_scan`` plugin events.

    Returns:
        Dict[str, Any]: A dictionary with the operation result.
        On success: ``{"status": "success", "message": "<summary_message>", "details": ScanResultDict}``
        where ``ScanResultDict`` contains keys like:
        ``"total_entries_in_logs"`` (int),
        ``"unique_players_submitted_for_saving"`` (int),
        ``"actually_saved_or_updated_in_db"`` (int),
        ``"scan_errors"`` (List[Dict[str, str]]).
        On error: ``{"status": "error", "message": "<error_message>"}``.

    Raises:
        BSMError: Can be raised by the underlying manager method, e.g.,
            :class:`~.error.AppFileNotFoundError` if the main server base directory
            is misconfigured, or :class:`~.error.FileOperationError` if the
            final save to the database fails. Individual server scan errors
            are reported within the "details" part of a successful response.
    """
    logger.info("API: Request to scan all server logs and update player DB.")

    try:
        # Delegate the entire discovery and saving process to the core manager.
        scan_result = (
            app_context.manager.discover_and_store_players_from_all_server_logs(
                app_context
            )
        )

        # Format a comprehensive success message from the scan results.
        message = (
            f"Player DB update complete. "
            f"Entries found in logs: {scan_result['total_entries_in_logs']}. "
            f"Unique players submitted: {scan_result['unique_players_submitted_for_saving']}. "
            f"Actually saved/updated: {scan_result['actually_saved_or_updated_in_db']}."
        )
        if scan_result["scan_errors"]:
            message += f" Scan errors encountered for: {scan_result['scan_errors']}"

        return {"status": "success", "message": message, "details": scan_result}

    except BSMError as e:
        # Handle application-specific errors during the scan.
        return {
            "status": "error",
            "message": f"An error occurred during player scan: {str(e)}",
        }

    except Exception as e:
        # Handle any other unexpected errors.
        logger.error(f"API: Unexpected error scanning for players: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"An unexpected error occurred during player scan: {str(e)}",
        }
