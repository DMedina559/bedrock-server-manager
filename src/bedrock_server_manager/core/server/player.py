"""Bedrock player component."""

import asyncio
import logging
import os
import re
from typing import TYPE_CHECKING, Dict, Iterator, List, Optional, Tuple

from ...error import FileOperationError
from ...logging import log_operation_error

if TYPE_CHECKING:
    from ..bedrock_server import BedrockServer


class ServerPlayers:
    """Player operations for one Bedrock server."""

    def __init__(self, server: "BedrockServer") -> None:
        self.server = server
        self.logger = logging.LoggerAdapter(
            logging.getLogger(__name__), {"server_name": server.server_name}
        )
        self._log_file_cursor = 0
        self._scan_log_cursor = 0

    def _parse_player_log_events(
        self, start_cursor: int = 0
    ) -> Iterator[Tuple[Optional[str], Optional[str], Optional[str], int]]:
        """Yield ``(event, name, XUID, cursor)`` records from a byte offset.

        Leave incomplete log lines for the next read.
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
            raise FileOperationError(
                f"Could not scan historical player log: {e}"
            ) from e

    async def scan_log_for_players(
        self, incremental: bool = False
    ) -> List[Dict[str, str]]:
        """Return unique ``name`` and ``xuid`` records found in the server log.

        Incremental reads resume at the saved cursor; missing logs produce an empty
        list.
        """
        log_file = self.server.paths.server_log_path
        self.logger.debug(
            "Server '%s': Scanning log file for players: %s (incremental=%s)",
            self.server.server_name,
            log_file,
            incremental,
        )
        identity = await asyncio.to_thread(
            lambda: os.stat(log_file) if os.path.isfile(log_file) else None
        )
        file_key = (identity.st_dev, identity.st_ino) if identity is not None else None
        if getattr(self, "_scan_identity", None) != file_key or (
            identity and identity.st_size < self._scan_log_cursor
        ):
            self._scan_log_cursor = 0
        self._scan_identity = file_key
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
                self.logger.debug(
                    "Server '%s': Found %s unique player(s) in log.",
                    self.server.server_name,
                    len(found_players),
                )
            return found_players
        except OSError as e:
            log_operation_error(
                self.logger,
                "Server '%s': Failed to read log file '%s' for player scanning: %s",
                self.server.server_name,
                log_file,
                e,
                error=e,
            )
            raise FileOperationError(
                f"Could not read log file for player scanning: {e}"
            ) from e

    async def update_online_players(self) -> List[Dict[str, str]]:
        """Update online-player records from new complete log lines.

        Return name/XUID records and retain the cursor. Clear players when the
        server is stopped.
        """
        await self.server.is_running()
        # Compatibility accessor: live presence is owned by the output consumer.
        return self.server.players

    def reset(self) -> None:
        """Reset both log consumers when the process starts or stops."""
        self._log_file_cursor = 0
        self._scan_log_cursor = 0
