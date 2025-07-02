# bedrock_server_manager/core/server/player_mixin.py
"""
Provides the :class:`.ServerPlayerMixin` for the
:class:`~.core.bedrock_server.BedrockServer` class.

This mixin is responsible for scanning a server's log files (typically
``server_output.txt``) to identify and extract player connection information.
Specifically, it looks for lines indicating a player connection to parse out
player gamertags and their corresponding XUIDs. This information can be used,
for example, to populate a player database or track server activity.
"""
import os
import re
from typing import List, Dict, TYPE_CHECKING, Any

# Local application imports.
from bedrock_server_manager.core.server.base_server_mixin import BedrockServerBaseMixin
from bedrock_server_manager.error import FileOperationError

if TYPE_CHECKING:
    pass


class ServerPlayerMixin(BedrockServerBaseMixin):
    """Provides methods for discovering player information by scanning server logs.

    This mixin extends :class:`.BedrockServerBaseMixin` and adds the capability
    to parse the server's log file (typically located at
    :attr:`~.BedrockServerBaseMixin.server_log_path`) for entries that indicate
    player connections. It extracts player gamertags and their XUIDs from these
    log entries.

    The primary method offered is :meth:`.scan_log_for_players`, which performs
    this scanning operation.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initializes the ServerPlayerMixin.

        Calls ``super().__init__(*args, **kwargs)`` to participate in cooperative
        multiple inheritance. It relies on attributes initialized by
        :class:`.BedrockServerBaseMixin`, such as `server_name`,
        `server_log_path` (used by :meth:`.scan_log_for_players`), and `logger`.

        Args:
            *args (Any): Variable length argument list passed to `super()`.
            **kwargs (Any): Arbitrary keyword arguments passed to `super()`.
        """
        super().__init__(*args, **kwargs)
        # Attributes from BedrockServerBaseMixin are available.

    def scan_log_for_players(self) -> List[Dict[str, str]]:
        """Scans the server's log file for player connection entries to extract gamertags and XUIDs.

        This method reads the server's primary output log file (obtained via
        :attr:`~.BedrockServerBaseMixin.server_log_path`) line by line. It uses a
        regular expression to find lines matching the standard Bedrock server
        message for player connections, which typically looks like:
        "Player connected: <Gamertag>, xuid: <XUID>".

        It collects unique players based on their XUID to avoid duplicates from
        multiple connections by the same player within the log.

        Returns:
            List[Dict[str, str]]: A list of unique player data dictionaries found
            in the log. Each dictionary has two keys:

                - "name" (str): The player's gamertag.
                - "xuid" (str): The player's Xbox User ID (XUID).

            Returns an empty list if the log file doesn't exist, is empty, or if
            no player connection entries are found.

        Raises:
            FileOperationError: If an OS-level error occurs while trying to read
                the log file (e.g., permission issues).
        """
        log_file = self.server_log_path  # This property is from BaseMixin.
        self.logger.debug(
            f"Server '{self.server_name}': Scanning log file for players: {log_file}"
        )

        if not os.path.isfile(log_file):
            self.logger.warning(
                f"Log file not found or is not a file: {log_file} for server '{self.server_name}'."
            )
            return []

        players_data: List[Dict[str, str]] = []
        # Use a set to track XUIDs and ensure each player is only added once per scan.
        unique_xuids = set()

        try:
            # Open the log file with error handling for encoding issues.
            with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                for line_number, line_content in enumerate(f, 1):
                    # Regex to find the "Player connected" line and capture name and XUID.
                    match = re.search(
                        r"Player connected:\s*([^,]+),\s*xuid:\s*(\d+)",
                        line_content,
                        re.IGNORECASE,
                    )
                    if match:
                        player_name, xuid = (
                            match.group(1).strip(),
                            match.group(2).strip(),
                        )
                        # Only add the player if they haven't been found in this scan yet.
                        if xuid not in unique_xuids:
                            players_data.append({"name": player_name, "xuid": xuid})
                            unique_xuids.add(xuid)
                            self.logger.debug(
                                f"Found player in log: Name='{player_name}', XUID='{xuid}'"
                            )
        except OSError as e:
            self.logger.error(
                f"Error reading log file '{log_file}' for server '{self.server_name}': {e}",
                exc_info=True,
            )
            raise FileOperationError(
                f"Error reading log file '{log_file}' for server '{self.server_name}': {e}"
            ) from e

        num_found = len(players_data)
        if num_found > 0:
            self.logger.info(
                f"Found {num_found} unique player(s) in log for server '{self.server_name}'."
            )
        else:
            self.logger.debug(
                f"No new unique players found in log for server '{self.server_name}'."
            )

        return players_data
