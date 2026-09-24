from typing import Any, Dict, List, Optional

import aiofiles.ospath

from ...core.player import get_known_players
from ...error import (
    AppFileNotFoundError,
    ConfigParseError,
    FileOperationError,
    MissingArgumentError,
    UserInputError,
)
from ...utils.io import load_json, save_json
from .base_server_mixin import BedrockServerBaseMixin


class ServerPermissionsMixin(BedrockServerBaseMixin):
    """Provides methods for managing the permissions.json configuration."""

    async def set_player_permission(
        self, xuid: str, permission_level: str, player_name: Optional[str] = None
    ) -> None:
        """Sets the permission level for a player asynchronously."""
        if not await aiofiles.ospath.isdir(self.server_dir):
            raise AppFileNotFoundError(self.server_dir, "Server directory")
        if not xuid:
            raise MissingArgumentError("Player XUID cannot be empty.")
        if not permission_level:
            raise MissingArgumentError("Permission level cannot be empty.")

        perm_level_lower = permission_level.lower()
        valid_perms = ("operator", "member", "visitor")
        if perm_level_lower not in valid_perms:
            raise UserInputError(
                f"Invalid permission '{perm_level_lower}'. Must be one of: {valid_perms}"
            )

        self.logger.info(
            f"Server '{self.server_name}': Setting permission for XUID '{xuid}' to '{perm_level_lower}'."
        )

        permissions_list: List[Dict[str, Any]] = []
        if await aiofiles.ospath.isfile(self.permissions_json_path):
            try:
                loaded_data = await load_json(self.permissions_json_path)
                if isinstance(loaded_data, list):
                    permissions_list = loaded_data
                elif loaded_data:
                    self.logger.warning(
                        f"Permissions file '{self.permissions_json_path}' is not a list. Overwriting."
                    )
            except ValueError as e:
                self.logger.warning(
                    f"Invalid JSON in permissions '{self.permissions_json_path}'. Overwriting. Error: {e}"
                )
            except OSError as e:
                raise FileOperationError(
                    f"Failed to read permissions '{self.permissions_json_path}': {e}"
                ) from e

        entry_found = False
        modified = False
        for entry in permissions_list:
            if isinstance(entry, dict) and entry.get("xuid") == xuid:
                entry_found = True
                if entry.get("permission") != perm_level_lower:
                    entry["permission"] = perm_level_lower
                    modified = True
                if player_name and entry.get("name") != player_name:
                    entry["name"] = player_name
                    modified = True
                break

        if not entry_found:
            effective_name = player_name if player_name else xuid
            permissions_list.append(
                {"permission": perm_level_lower, "xuid": xuid, "name": effective_name}
            )
            modified = True

        if modified:
            try:
                lock = self.get_file_lock(self.permissions_json_path)
                async with lock:
                    await save_json(
                        permissions_list, self.permissions_json_path, indent=4
                    )
                self.logger.info(
                    f"Successfully updated permissions for XUID '{xuid}' for '{self.server_name}'."
                )
            except OSError as e:
                raise FileOperationError(
                    f"Failed to write permissions '{self.permissions_json_path}': {e}"
                ) from e
        else:
            self.logger.info(
                f"No changes needed for XUID '{xuid}' permissions for '{self.server_name}'."
            )

    async def get_formatted_permissions(
        self, db_session_manager: Any
    ) -> List[Dict[str, Any]]:
        """Retrieves permissions and maps XUIDs to known player names asynchronously."""
        if not await aiofiles.ospath.isdir(self.server_dir):
            raise AppFileNotFoundError(self.server_dir, "Server directory")
        if not await aiofiles.ospath.isfile(self.permissions_json_path):
            raise AppFileNotFoundError(self.permissions_json_path, "Permissions file")

        self.logger.debug(
            f"Server '{self.server_name}': Reading and processing permissions from {self.permissions_json_path} asynchronously"
        )

        raw_permissions: List[Dict[str, Any]] = []
        try:
            loaded_data = await load_json(self.permissions_json_path)
            if isinstance(loaded_data, list):
                raw_permissions = loaded_data
            elif loaded_data:
                raise ConfigParseError("Permissions file content is not a list.")
        except ValueError as e:
            raise ConfigParseError(f"Invalid JSON in permissions file: {e}") from e
        except OSError as e:
            raise FileOperationError(
                f"OSError reading permissions file '{self.permissions_json_path}': {e}"
            ) from e

        try:
            known_players = await get_known_players(db_session_manager)
            player_map = {p["xuid"]: p["name"] for p in known_players}
        except Exception as e:
            self.logger.error(
                f"Error retrieving known players from database: {e}. Will use XUIDs as names where needed."
            )
            player_map = {}

        processed_list: List[Dict[str, Any]] = []
        for entry in raw_permissions:
            if isinstance(entry, dict) and "xuid" in entry and "permission" in entry:
                xuid = str(entry["xuid"])
                name = player_map.get(
                    xuid, entry.get("name", f"Unknown (XUID: {xuid})")
                )
                processed_list.append(
                    {
                        "xuid": xuid,
                        "name": name,
                        "permission_level": str(entry["permission"]),
                    }
                )
            else:
                self.logger.warning(
                    f"Skipping malformed entry in '{self.permissions_json_path}': {entry}"
                )

        processed_list.sort(key=lambda p: str(p.get("name", "")).lower())
        return processed_list
