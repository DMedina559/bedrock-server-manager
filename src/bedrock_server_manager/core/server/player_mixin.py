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
from typing import TYPE_CHECKING, Any, Dict, Iterator, List, Optional, Tuple

from ...error import FileOperationError
from .base_server_mixin import BedrockServerBaseMixin

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

    def _parse_player_log_events(  # noqa: C901
        self, start_cursor: int = 0
    ) -> Iterator[Tuple[Optional[str], Optional[str], Optional[str], int]]:
        """A generator that safely and incrementally parses the server log file.

        Reads lines in binary mode to accurately handle incomplete lines from active flushes,
        and yields player connection and disconnection events.

        Args:
            start_cursor (int): The byte offset to start reading from.

        Yields:
            Tuple[str, str, str, int]: A tuple containing the event type ("connect" or "disconnect"),
            the player's name, the player's XUID, and the cursor position right after reading the line.
        """
        log_file = self.server_log_path
        if not os.path.isfile(log_file):
            return

        try:
            with open(log_file, "rb") as f:
                f.seek(start_cursor)

                while True:
                    cursor_before_line = f.tell()
                    line_bytes = f.readline()

                    if not line_bytes:
                        # Reached EOF safely
                        yield None, None, None, f.tell()
                        break

                    if not line_bytes.endswith(b"\n"):
                        # Incomplete line, revert cursor and stop parsing for now
                        f.seek(cursor_before_line)
                        yield None, None, None, f.tell()
                        break

                    line = line_bytes.decode("utf-8", errors="ignore")

                    # Match connection
                    match_conn = re.search(
                        r"Player connected:\s*([^,]+),\s*xuid:\s*(\d+)",
                        line,
                        re.IGNORECASE,
                    )
                    if match_conn:
                        name, xuid = (
                            match_conn.group(1).strip(),
                            match_conn.group(2).strip(),
                        )
                        if name and xuid:
                            yield "connect", name, xuid, f.tell()
                    else:
                        # Match disconnection
                        match_disconn = re.search(
                            r"Player disconnected:\s*([^,]+),\s*xuid:\s*(\d+)",
                            line,
                            re.IGNORECASE,
                        )
                        if match_disconn:
                            xuid = match_disconn.group(2).strip()
                            # Disconnect log provides name and xuid in same format
                            name = match_disconn.group(1).strip()
                            if name and xuid:
                                yield "disconnect", name, xuid, f.tell()

        except OSError as e:
            self.logger.error(
                f"Error parsing log file '{log_file}' for server '{self.server_name}': {e}",
                exc_info=True,
            )

    def scan_log_for_players(self, incremental: bool = False) -> List[Dict[str, str]]:
        """Scans the server's log file for player connection entries to extract gamertags and XUIDs.

        This method reads the server's primary output log file (obtained via
        :attr:`~.BedrockServerBaseMixin.server_log_path`) to find player connections.
        It collects unique players based on their XUID to avoid duplicates.

        Args:
            incremental (bool): If True, starts reading from the last recorded position
                instead of the beginning. Useful for periodic polling to save memory.

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
        if not hasattr(self, "_scan_log_cursor"):
            self._scan_log_cursor = 0

        log_file = self.server_log_path
        self.logger.debug(
            f"Server '{self.server_name}': Scanning log file for players: {log_file} (incremental={incremental})"
        )

        players_data: List[Dict[str, str]] = []
        unique_xuids = set()

        start_pos = self._scan_log_cursor if incremental else 0

        try:
            for (
                event_type,
                player_name,
                xuid,
                new_cursor,
            ) in self._parse_player_log_events(start_pos):
                if (
                    event_type == "connect"
                    and player_name is not None
                    and xuid is not None
                    and xuid not in unique_xuids
                ):
                    players_data.append({"name": player_name, "xuid": xuid})
                    unique_xuids.add(xuid)
                    self.logger.debug(
                        f"Found player in log: Name='{player_name}', XUID='{xuid}'"
                    )
                if incremental:
                    self._scan_log_cursor = new_cursor
        except Exception as e:
            # We wrap it in FileOperationError to match old behavior
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

    def update_online_players(self) -> List[Dict[str, str]]:
        """Incrementally parses the server log to update the list of currently online players.

        Reads new lines from the log file starting from the last known cursor position
        (`self._log_file_cursor`), updates the `self.players` attribute, and saves the new cursor position.

        Returns:
            List[Dict[str, str]]: The updated list of dictionaries for each currently
            online player, containing their "name" and "uuid" (XUID).
        """
        # Ensure attributes exist
        if not hasattr(self, "_log_file_cursor"):
            self._log_file_cursor = 0
        if not hasattr(self, "players"):
            self.players: List[Dict[str, str]] = []

        # Map current players by xuid for quick O(1) updates
        online_players: Dict[str, str] = {p["uuid"]: p["name"] for p in self.players}

        for event_type, name, xuid, new_cursor in self._parse_player_log_events(
            self._log_file_cursor
        ):
            if event_type == "connect" and xuid and name:
                online_players[xuid] = name
            elif event_type == "disconnect" and xuid:
                if xuid in online_players:
                    del online_players[xuid]

            # Update cursor position to right after the parsed line
            self._log_file_cursor = new_cursor

        # Update self.players array and return it
        self.players = [
            {"name": name, "uuid": xuid} for xuid, name in online_players.items()
        ]
        return self.players
