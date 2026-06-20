import json
import os
from typing import Any, Dict, List

from ...error import (
    AppFileNotFoundError,
    ConfigParseError,
    FileOperationError,
    MissingArgumentError,
)
from .base_server_mixin import BedrockServerBaseMixin


class ServerAllowlistMixin(BedrockServerBaseMixin):
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
