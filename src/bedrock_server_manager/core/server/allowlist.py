"""Bedrock allowlist component."""

import logging
from typing import TYPE_CHECKING, Any, Dict, List

import aiofiles.ospath

from ...error import (
    AppFileNotFoundError,
    ConfigParseError,
    FileOperationError,
    MissingArgumentError,
)
from ...utils.io import load_json, save_json
from ..data import ALLOWLIST

if TYPE_CHECKING:
    from ..bedrock_server import BedrockServer


class ServerAllowlist:
    """Allowlist operations for one Bedrock server."""

    def __init__(self, server: "BedrockServer") -> None:
        self.server = server
        self.logger = logging.LoggerAdapter(
            logging.getLogger(__name__), {"server_name": server.server_name}
        )

    async def get_allowlist(self) -> List[Dict[str, Any]]:
        """Reads the `allowlist.json` file asynchronously and returns its contents."""
        self.logger.debug(
            "Server '%s': Loading allowlist from %s",
            self.server.server_name,
            self.server.paths.allowlist_json_path,
        )
        if not await aiofiles.ospath.isdir(self.server.paths.server_dir):
            raise AppFileNotFoundError(self.server.paths.server_dir, "Server directory")
        allowlist_entries: List[Dict[str, Any]] = []
        if await aiofiles.ospath.isfile(self.server.paths.allowlist_json_path):
            file_size = await aiofiles.ospath.getsize(
                self.server.paths.allowlist_json_path
            )
            if file_size == 0:
                return []
            try:
                loaded_data = await load_json(self.server.paths.allowlist_json_path)
                if isinstance(loaded_data, list):
                    allowlist_entries = [
                        entry.model_dump(mode="json", exclude_unset=True)
                        for entry in ALLOWLIST.validate_python(loaded_data)
                    ]
                elif loaded_data:
                    self.logger.warning(
                        "Allowlist file '%s' is not a JSON list. Treating as empty.",
                        self.server.paths.allowlist_json_path,
                    )
            except ValueError as e:
                raise ConfigParseError(
                    f"Invalid JSON in allowlist '{self.server.paths.allowlist_json_path}': {e}"
                ) from e
            except OSError as e:
                raise FileOperationError(
                    f"Failed to read allowlist '{self.server.paths.allowlist_json_path}': {e}"
                ) from e
        else:
            self.logger.debug(
                "Allowlist file '%s' does not exist. Returning empty list.",
                self.server.paths.allowlist_json_path,
            )
        return allowlist_entries

    async def add_to_allowlist(self, players_to_add: List[Dict[str, Any]]) -> int:
        """Adds players to the allowlist asynchronously."""
        async with self.server.get_file_lock(self.server.paths.allowlist_json_path):
            if not isinstance(players_to_add, list):
                raise TypeError(
                    "Input 'players_to_add' must be a list of dictionaries."
                )
            if not await aiofiles.ospath.isdir(self.server.paths.server_dir):
                raise AppFileNotFoundError(
                    self.server.paths.server_dir, "Server directory"
                )
            self.logger.debug(
                "Server '%s': Adding %s player(s) to allowlist.",
                self.server.server_name,
                len(players_to_add),
            )
            current_allowlist = await self.get_allowlist()
            existing_names_lower = {
                p.get("name", "").lower()
                for p in current_allowlist
                if isinstance(p, dict) and p.get("name")
            }
            added_count = 0
            for player_entry in players_to_add:
                if (
                    not isinstance(player_entry, dict)
                    or not player_entry.get("name")
                    or (not isinstance(player_entry.get("name"), str))
                ):
                    self.logger.warning(
                        "Skipping invalid player entry for allowlist: %s", player_entry
                    )
                    continue
                player_name = player_entry["name"]
                if player_name.lower() not in existing_names_lower:
                    if "ignoresPlayerLimit" not in player_entry:
                        player_entry["ignoresPlayerLimit"] = False
                    current_allowlist.append(player_entry)
                    existing_names_lower.add(player_name.lower())
                    added_count += 1
                    self.logger.debug(
                        "Player '%s' prepared for allowlist addition.", player_name
                    )
                else:
                    self.logger.debug(
                        "Player '%s' already in allowlist or added in this batch. Skipping.",
                        player_name,
                    )
            if added_count > 0:
                try:
                    lock = self.server.get_file_lock(
                        self.server.paths.allowlist_json_path
                    )
                    async with lock:
                        await save_json(
                            current_allowlist,
                            self.server.paths.allowlist_json_path,
                            indent=4,
                        )
                    self.logger.info(
                        "Successfully updated allowlist for '%s'. %s players added.",
                        self.server.server_name,
                        added_count,
                    )
                except OSError as e:
                    raise FileOperationError(
                        f"Failed to write allowlist '{self.server.paths.allowlist_json_path}': {e}"
                    ) from e
            else:
                self.logger.debug(
                    "No new players added to allowlist for '%s'.",
                    self.server.server_name,
                )
            return added_count

    async def remove_from_allowlist(self, player_name_to_remove: str) -> bool:
        """Removes a player from the allowlist asynchronously."""
        async with self.server.get_file_lock(self.server.paths.allowlist_json_path):
            if not isinstance(player_name_to_remove, str) or not player_name_to_remove:
                raise MissingArgumentError(
                    "Player name to remove cannot be empty and must be a string."
                )
            if not await aiofiles.ospath.isdir(self.server.paths.server_dir):
                raise AppFileNotFoundError(
                    self.server.paths.server_dir, "Server directory"
                )
            self.logger.debug(
                "Server '%s': Removing player '%s' from allowlist.",
                self.server.server_name,
                player_name_to_remove,
            )
            current_allowlist = await self.get_allowlist()
            name_lower_to_remove = player_name_to_remove.lower()
            updated_allowlist = [
                p
                for p in current_allowlist
                if not (
                    isinstance(p, dict)
                    and p.get("name", "").lower() == name_lower_to_remove
                )
            ]
            if len(updated_allowlist) < len(current_allowlist):
                try:
                    lock = self.server.get_file_lock(
                        self.server.paths.allowlist_json_path
                    )
                    async with lock:
                        await save_json(
                            updated_allowlist,
                            self.server.paths.allowlist_json_path,
                            indent=4,
                        )
                    self.logger.info(
                        "Successfully removed '%s' from allowlist for '%s'.",
                        player_name_to_remove,
                        self.server.server_name,
                    )
                    return True
                except OSError as e:
                    raise FileOperationError(
                        f"Failed to write allowlist '{self.server.paths.allowlist_json_path}': {e}"
                    ) from e
            else:
                self.logger.debug(
                    "Player '%s' not found in allowlist for '%s'.",
                    player_name_to_remove,
                    self.server.server_name,
                )
                return False
