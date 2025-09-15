import logging
import os
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from bedrock_server_manager.context import AppContext
from bedrock_server_manager.db.models import Player
from bedrock_server_manager.error import (
    AppFileNotFoundError,
    FileOperationError,
    UserInputError,
)


logger = logging.getLogger(__name__)


class PlayerMixin:
    """
    Mixin class for BedrockServerManager that handles player database management.
    """

    def parse_player_cli_argument(self, player_string: str) -> None:
        """Parses a comma-separated string of 'player_name:xuid' pairs and saves them to the database.

        This utility method is designed to process player data provided as a
        single string, typically from a command-line argument. Each player entry
        in the string should be in the format "PlayerName:PlayerXUID", and multiple
        entries should be separated by commas. Whitespace around names, XUIDs,
        commas, and colons is generally handled.

        Example:
            ``"Player One:12345, PlayerTwo:67890"``

        Args:
            player_string (str): The comma-separated string of player data.
                If empty or not a string, an empty list is returned.

        Raises:
            UserInputError: If any player pair within the string does not conform
                to the "name:xuid" format, or if a name or XUID is empty after stripping.
        """
        if not player_string or not isinstance(player_string, str):
            return
        logger.debug(f"BSM: Parsing player argument string: '{player_string}'")
        player_list: List[Dict[str, str]] = []
        player_pairs = [
            pair.strip() for pair in player_string.split(",") if pair.strip()
        ]
        for pair in player_pairs:
            player_data = pair.split(":", 1)
            if len(player_data) != 2:
                raise UserInputError(
                    f"Invalid player data format: '{pair}'. Expected 'name:xuid'."
                )
            player_name, player_id = player_data[0].strip(), player_data[1].strip()
            if not player_name or not player_id:
                raise UserInputError(f"Name and XUID cannot be empty in '{pair}'.")
            player_list.append({"name": player_name.strip(), "xuid": player_id.strip()})

        self.save_player_data(player_list)

    def save_player_data(self, players_data: List[Dict[str, str]]) -> int:
        """Saves or updates player data in the database.

        This method merges the provided ``players_data`` with any existing player
        data in the database.

        The merging logic is as follows:

            - If a player's XUID from ``players_data`` already exists in the database,
              their entry (name and XUID) is updated if different.
            - If a player's XUID is new, their entry is added to the database.

        Args:
            players_data (List[Dict[str, str]]): A list of player dictionaries.
                Each dictionary must contain string values for ``"name"`` and ``"xuid"`` keys.
                Both name and XUID must be non-empty.

        Returns:
            int: The total number of players that were newly added or had their
            existing entry updated. Returns 0 if no changes were made.

        Raises:
            UserInputError: If ``players_data`` is not a list, or if any dictionary
                within it does not conform to the required format (missing keys,
                non-string values, or empty name/XUID).
        """
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

        with self.settings.db.session_manager() as db:
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
                        f"BSM: Saved/Updated players. Added: {added_count}, Updated: {updated_count}."
                    )
                    return added_count + updated_count

                logger.debug("BSM: No new or updated player data to save.")
                return 0
            except Exception as e:
                db.rollback()
                raise e

    def get_known_players(self) -> List[Dict[str, str]]:
        """Retrieves all known players from the database.

        Returns:
            List[Dict[str, str]]: A list of player dictionaries, where each
            dictionary typically contains ``"name"`` and ``"xuid"`` keys.
        """
        with self.settings.db.session_manager() as db:
            players = db.query(Player).all()
            return [
                {"name": player.player_name, "xuid": player.xuid} for player in players
            ]

    def discover_and_store_players_from_all_server_logs(
        self, app_context: "AppContext"
    ) -> Dict[str, Any]:
        """Scans all server logs for player data and updates the central player database.

        This comprehensive method performs the following actions:

            1. Iterates through all subdirectories within the application's base server
               directory (defined by ``settings['paths.servers']``).
            2. For each subdirectory, it attempts to instantiate a
               :class:`~.core.bedrock_server.BedrockServer` object.
            3. If the server instance is valid and installed, it calls the server's
               :meth:`~.core.server.player_mixin.ServerPlayerMixin.scan_log_for_players`
               method to extract player names and XUIDs from its logs.
            4. All player data discovered from all server logs is aggregated.
            5. Unique player entries (based on XUID) are then saved to the database
               using :meth:`.save_player_data`.

        Args:
            None

        Returns:
            Dict[str, Any]: A dictionary summarizing the discovery and saving operation,
            containing the following keys:

                - ``"total_entries_in_logs"`` (int): The total number of player entries
                  (possibly non-unique) found across all server logs.
                - ``"unique_players_submitted_for_saving"`` (int): The number of unique
                  player entries (by XUID) that were attempted to be saved.
                - ``"actually_saved_or_updated_in_db"`` (int): The number of players
                  that were newly added or updated in the database
                  by the :meth:`.save_player_data` call.
                - ``"scan_errors"`` (List[Dict[str, str]]): A list of dictionaries,
                  where each entry represents an error encountered while scanning a
                  specific server's logs or saving the global player DB. Each error
                  dictionary contains ``"server"`` (str, server name or "GLOBAL_PLAYER_DB")
                  and ``"error"`` (str, error message).

        Raises:
            AppFileNotFoundError: If the main server base directory
                (``settings['paths.servers']``) is not configured or does not exist.
            FileOperationError: If the final save operation to the database
                (via :meth:`.save_player_data`) fails.
                Note that errors during individual server log scans are caught and
                reported in the ``"scan_errors"`` part of the return value.
        """
        if not self._base_dir or not os.path.isdir(self._base_dir):
            raise AppFileNotFoundError(str(self._base_dir), "Server base directory")

        all_discovered_from_logs: List[Dict[str, str]] = []
        scan_errors_details: List[Dict[str, str]] = []

        logger.info(
            f"BSM: Starting discovery of players from all server logs in '{self._base_dir}'."
        )

        for server_name_candidate in os.listdir(self._base_dir):
            potential_server_path = os.path.join(self._base_dir, server_name_candidate)
            if not os.path.isdir(potential_server_path):
                continue

            logger.debug(f"BSM: Processing potential server '{server_name_candidate}'.")
            try:
                # Instantiate a BedrockServer to use its encapsulated logic.
                server_instance = app_context.get_server(server_name_candidate)

                # Validate it's a real server before trying to scan its logs.
                if not server_instance.is_installed():
                    logger.debug(
                        f"BSM: '{server_name_candidate}' is not a valid Bedrock server installation. Skipping log scan."
                    )
                    continue

                # Use the instance's own method to scan its log file.
                players_in_log = server_instance.scan_log_for_players()
                if players_in_log:
                    all_discovered_from_logs.extend(players_in_log)
                    logger.debug(
                        f"BSM: Found {len(players_in_log)} players in log for server '{server_name_candidate}'."
                    )

            except FileOperationError as e:
                logger.warning(
                    f"BSM: Error scanning log for server '{server_name_candidate}': {e}"
                )
                scan_errors_details.append(
                    {"server": server_name_candidate, "error": str(e)}
                )
            except Exception as e_instantiate:
                logger.error(
                    f"BSM: Error processing server '{server_name_candidate}' for player discovery: {e_instantiate}",
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
            unique_players_to_save_map = {
                p["xuid"]: p for p in all_discovered_from_logs
            }
            unique_players_to_save_list = list(unique_players_to_save_map.values())
            try:
                # Save all unique players to the central database.
                saved_count = self.save_player_data(unique_players_to_save_list)
            except (FileOperationError, Exception) as e_save:
                logger.error(
                    f"BSM: Critical error saving player data to global DB: {e_save}",
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
