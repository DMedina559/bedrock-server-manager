import asyncio
import json
import os
import typing
from typing import Any, Dict, List

import aiofiles
import aiofiles.ospath

from ...error import (
    AppFileNotFoundError,
    ConfigParseError,
    FileOperationError,
    MissingArgumentError,
    UserInputError,
)
from .base_server_mixin import BedrockServerBaseMixin


class ServerAllowlistMixin(BedrockServerBaseMixin):
    """Provides methods for managing the allowlist.json configuration."""

    @typing.no_type_check
    async def async_get_allowlist(self) -> List[Dict[str, Any]]:  # type: ignore
        """Reads the `allowlist.json` file asynchronously and returns its contents."""

        self.logger.debug(
            f"Reading allowlist from: {self.allowlist_path} asynchronously"
        )
        if not await aiofiles.ospath.isfile(self.allowlist_path):
            raise AppFileNotFoundError(self.allowlist_path, "allowlist.json")
        try:
            async with aiofiles.open(self.allowlist_path, "r", encoding="utf-8") as f:
                content = await f.read()
                data = json.loads(content)
                self.logger.debug(
                    f"Successfully loaded {len(data)} entries from allowlist.json for '{self.server_name}'"
                )
                return data
        except json.JSONDecodeError as e:
            self.logger.error(
                f"JSON decode error in {self.allowlist_path} for '{self.server_name}': {e}"
            )
            return []
        except Exception as e:
            self.logger.error(
                f"Error reading {self.allowlist_path} for '{self.server_name}': {e}"
            )
            return []

    @typing.no_type_check
    async def async_add_to_allowlist(self, players_to_add: List[Dict[str, Any]]) -> int:  # type: ignore
        """Adds players to the allowlist asynchronously."""

        if not isinstance(players_to_add, list):
            raise UserInputError("Input must be a list of player dictionaries.")

        current_list = await self.async_get_allowlist()
        # Ensure name comparison is case-insensitive for adding
        existing_names_lower = {p.get("name", "").lower() for p in current_list}
        added_count = 0

        for new_player in players_to_add:
            # Basic validation
            if not isinstance(new_player, dict) or "name" not in new_player:
                self.logger.warning(
                    f"Skipping invalid player entry in add_to_allowlist: {new_player}"
                )
                continue

            new_name = str(new_player.get("name")).strip()
            if not new_name:
                self.logger.warning("Skipping player entry with empty name.")
                continue

            if new_name.lower() not in existing_names_lower:
                current_list.append(new_player)
                existing_names_lower.add(new_name.lower())
                added_count += 1
                self.logger.debug(
                    f"Added '{new_name}' to allowlist for '{self.server_name}'."
                )
            else:
                self.logger.debug(
                    f"Player '{new_name}' already in allowlist for '{self.server_name}'. Skipping."
                )

        if added_count > 0:
            try:
                async with aiofiles.open(
                    self.allowlist_path, "w", encoding="utf-8"
                ) as f:
                    content = json.dumps(current_list, indent=4)
                    await f.write(content)
                self.logger.info(
                    f"Successfully added {added_count} player(s) to allowlist for '{self.server_name}'."
                )

                # If the server is running, we also need to reload the allowlist.
                if hasattr(self, "async_is_running"):
                    is_running = await self.async_is_running()
                else:

                    is_running = await asyncio.to_thread(self.is_running)

                if is_running:
                    if hasattr(self, "async_send_command"):
                        await self.async_send_command("allowlist reload")
                    else:

                        await asyncio.to_thread(self.send_command, "allowlist reload")
                    self.logger.info(
                        f"Reloaded allowlist for running server '{self.server_name}'."
                    )

            except Exception as e:
                self.logger.error(
                    f"Failed to write updated allowlist to {self.allowlist_path} for '{self.server_name}': {e}"
                )
                return 0

        return added_count

    @typing.no_type_check
    async def async_remove_from_allowlist(self, player_name_to_remove: str) -> bool:  # type: ignore
        """Removes a player from the allowlist asynchronously."""

        if not isinstance(player_name_to_remove, str) or not player_name_to_remove:
            raise UserInputError("Player name to remove must be a non-empty string.")

        current_list = await self.async_get_allowlist()
        original_length = len(current_list)

        name_to_remove_lower = player_name_to_remove.strip().lower()

        filtered_list = [
            p
            for p in current_list
            if str(p.get("name", "")).strip().lower() != name_to_remove_lower
        ]

        if len(filtered_list) < original_length:
            try:
                async with aiofiles.open(
                    self.allowlist_path, "w", encoding="utf-8"
                ) as f:
                    content = json.dumps(filtered_list, indent=4)
                    await f.write(content)
                self.logger.info(
                    f"Successfully removed '{player_name_to_remove}' from allowlist for '{self.server_name}'."
                )

                if hasattr(self, "async_is_running"):
                    is_running = await self.async_is_running()
                else:

                    is_running = await asyncio.to_thread(self.is_running)

                if is_running:
                    if hasattr(self, "async_send_command"):
                        await self.async_send_command("allowlist reload")
                    else:

                        await asyncio.to_thread(self.send_command, "allowlist reload")
                    self.logger.info(
                        f"Reloaded allowlist for running server '{self.server_name}'."
                    )

                return True
            except Exception as e:
                self.logger.error(
                    f"Failed to write updated allowlist to {self.allowlist_path} for '{self.server_name}': {e}"
                )
                return False
        else:
            self.logger.debug(
                f"Player '{player_name_to_remove}' not found in allowlist for '{self.server_name}'. No removal performed."
            )
            return False

    def get_allowlist(self) -> List[Dict[str, Any]]:
        self.logger.debug(
            f"Server '{self.server_name}': Loading allowlist from {self.allowlist_json_path}"
        )

        if not os.path.isdir(self.server_dir):
            raise AppFileNotFoundError(self.server_dir, "Server directory")

        allowlist_entries: List[Dict[str, Any]] = []
        if os.path.isfile(self.allowlist_json_path):
            try:
                with open(self.allowlist_json_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    if content.strip():
                        loaded_data = json.loads(content)
                        if isinstance(loaded_data, list):
                            allowlist_entries = loaded_data
                        else:
                            self.logger.warning(
                                f"Allowlist file '{self.allowlist_json_path}' is not a JSON list. Treating as empty."
                            )
            except ValueError as e:
                raise ConfigParseError(
                    f"Invalid JSON in allowlist '{self.allowlist_json_path}': {e}"
                ) from e
            except OSError as e:
                raise FileOperationError(
                    f"Failed to read allowlist '{self.allowlist_json_path}': {e}"
                ) from e
        else:
            self.logger.debug(
                f"Allowlist file '{self.allowlist_json_path}' does not exist. Returning empty list."
            )

        return allowlist_entries

    def add_to_allowlist(self, players_to_add: List[Dict[str, Any]]) -> int:
        if not isinstance(players_to_add, list):
            raise TypeError("Input 'players_to_add' must be a list of dictionaries.")
        if not os.path.isdir(self.server_dir):
            raise AppFileNotFoundError(self.server_dir, "Server directory")

        self.logger.info(
            f"Server '{self.server_name}': Adding {len(players_to_add)} player(s) to allowlist."
        )

        current_allowlist = self.get_allowlist()
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
                or not isinstance(player_entry.get("name"), str)
            ):
                self.logger.warning(
                    f"Skipping invalid player entry for allowlist: {player_entry}"
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
                    f"Player '{player_name}' prepared for allowlist addition."
                )
            else:
                self.logger.warning(
                    f"Player '{player_name}' already in allowlist or added in this batch. Skipping."
                )

        if added_count > 0:
            try:
                with open(self.allowlist_json_path, "w", encoding="utf-8") as f:
                    json.dump(current_allowlist, f, indent=4, sort_keys=True)
                self.logger.info(
                    f"Successfully updated allowlist for '{self.server_name}'. {added_count} players added."
                )
            except OSError as e:
                raise FileOperationError(
                    f"Failed to write allowlist '{self.allowlist_json_path}': {e}"
                ) from e
        else:
            self.logger.info(
                f"No new players added to allowlist for '{self.server_name}'."
            )
        return added_count

    def remove_from_allowlist(self, player_name_to_remove: str) -> bool:
        if not isinstance(player_name_to_remove, str) or not player_name_to_remove:
            raise MissingArgumentError(
                "Player name to remove cannot be empty and must be a string."
            )
        if not os.path.isdir(self.server_dir):
            raise AppFileNotFoundError(self.server_dir, "Server directory")

        self.logger.info(
            f"Server '{self.server_name}': Removing player '{player_name_to_remove}' from allowlist."
        )

        current_allowlist = self.get_allowlist()
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
                with open(self.allowlist_json_path, "w", encoding="utf-8") as f:
                    json.dump(updated_allowlist, f, indent=4, sort_keys=True)
                self.logger.info(
                    f"Successfully removed '{player_name_to_remove}' from allowlist for '{self.server_name}'."
                )
                return True
            except OSError as e:
                raise FileOperationError(
                    f"Failed to write allowlist '{self.allowlist_json_path}': {e}"
                ) from e
        else:
            self.logger.warning(
                f"Player '{player_name_to_remove}' not found in allowlist for '{self.server_name}'."
            )
            return False
