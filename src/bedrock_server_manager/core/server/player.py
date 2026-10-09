"""Bedrock player component."""

import asyncio
import os
import re
from typing import TYPE_CHECKING, Dict, Iterator, List, Optional, Tuple

from ...error import FileOperationError

if TYPE_CHECKING:
    from ..bedrock_server import BedrockServer


class ServerPlayers:
    """Player operations for one Bedrock server."""

    def __init__(self, server: "BedrockServer") -> None:
        self.server = server
        self._log_file_cursor = 0
        self._scan_log_cursor = 0

    def _parse_player_log_events(
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
        log_file = self.server.paths.server_log_path
        if not os.path.isfile(log_file):
            return
        try:
            with open(log_file, "rb") as f:
                f.seek(start_cursor)
                while True:
                    cursor_before_line = f.tell()
                    line_bytes = f.readline()
                    if not line_bytes:
                        yield (None, None, None, f.tell())
                        break
                    if not line_bytes.endswith(b"\n"):
                        f.seek(cursor_before_line)
                        yield (None, None, None, f.tell())
                        break
                    line = line_bytes.decode("utf-8", errors="ignore")
                    match_conn = re.search(
                        "Player connected:\\s*([^,]+?)(?:,\\s*|\\s+)xuid:\\s*(\\d+)",
                        line,
                        re.IGNORECASE,
                    )
                    if match_conn:
                        name, xuid = (
                            match_conn.group(1).strip(),
                            match_conn.group(2).strip(),
                        )
                        if name and xuid:
                            yield ("connect", name, xuid, f.tell())
                    else:
                        match_disconn = re.search(
                            "Player disconnected:\\s*([^,]+?)(?:,\\s*|\\s+)xuid:\\s*(\\d+)",
                            line,
                            re.IGNORECASE,
                        )
                        if match_disconn:
                            xuid = match_disconn.group(2).strip()
                            name = match_disconn.group(1).strip()
                            if name and xuid:
                                yield ("disconnect", name, xuid, f.tell())
        except OSError as e:
            self.server.logger.error(
                f"Error parsing log file '{log_file}' for server '{self.server.server_name}': {e}",
                exc_info=True,
            )

    async def scan_log_for_players(
        self, incremental: bool = False
    ) -> List[Dict[str, str]]:
        """Scans the server's log file for player connection entries to extract gamertags and XUIDs asynchronously.

        This method reads the server's primary output log file (obtained via
        :attr:`~.ServerResources.server_log_path`) to find player connections.
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
        log_file = self.server.paths.server_log_path
        self.server.logger.debug(
            f"Server '{self.server.server_name}': Scanning log file for players: {log_file} (incremental={incremental}) asynchronously"
        )
        start_pos = self._scan_log_cursor if incremental else 0
        unique_players = {}
        try:
            for event_type, name, xuid, new_cursor in await asyncio.to_thread(
                lambda: list(self._parse_player_log_events(start_pos))
            ):
                if event_type == "connect" and name and xuid:
                    unique_players[xuid] = name
                if incremental:
                    self._scan_log_cursor = new_cursor
            found_players = [
                {"name": name, "xuid": xuid} for xuid, name in unique_players.items()
            ]
            if found_players:
                self.server.logger.debug(
                    f"Server '{self.server.server_name}': Found {len(found_players)} unique player(s) in log."
                )
            return found_players
        except OSError as e:
            self.server.logger.error(
                f"Server '{self.server.server_name}': Failed to read log file '{log_file}' for player scanning: {e}"
            )
            raise FileOperationError(
                f"Could not read log file for player scanning: {e}"
            ) from e

    async def update_online_players(self) -> List[Dict[str, str]]:
        """Incrementally parses the server log to update the list of currently online players asynchronously.

        Reads new lines from the log file starting from the last known cursor position
        (`self._log_file_cursor`), updates the `self.players` attribute, and saves the new cursor position.

        Returns:
            List[Dict[str, str]]: The updated list of dictionaries for each currently
            online player, containing their "name" and "xuid".
        """
        is_running = await self.server.is_running()
        if not is_running:
            self.server.players = []
            return []
        online_players: Dict[str, str] = {}
        for p in self.server.players:
            if isinstance(p, dict):
                p_xuid = p.get("xuid")
                p_name = p.get("name")
                if p_xuid and p_name:
                    online_players[str(p_xuid)] = str(p_name)
        events = await asyncio.to_thread(
            lambda: list(self._parse_player_log_events(self._log_file_cursor))
        )
        for event_type, name, xuid, new_cursor in events:
            if event_type == "connect" and xuid and name:
                online_players[xuid] = name
            elif event_type == "disconnect" and xuid:
                if xuid in online_players:
                    del online_players[xuid]
            self._log_file_cursor = new_cursor
        setattr(
            self.server,
            "players",
            [{"name": name, "xuid": xuid} for xuid, name in online_players.items()],
        )
        return getattr(self.server, "players", [])

    def reset(self) -> None:
        """Reset both log consumers when the process starts or stops."""
        self._log_file_cursor = 0
        self._scan_log_cursor = 0
