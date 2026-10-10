"""Bedrock permissions component."""

import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import aiofiles.ospath

from ...core.player import get_known_players
from ...error import (
    AppFileNotFoundError,
    ConfigParseError,
    FileOperationError,
    MissingArgumentError,
    UserInputError,
)
from ...logging import log_operation_error
from ...utils.io import load_json, save_json
from ..data import PERMISSIONS

if TYPE_CHECKING:
    from ..bedrock_server import BedrockServer


class ServerPermissions:
    """Permissions operations for one Bedrock server."""

    def __init__(self, server: "BedrockServer") -> None:
        self.server = server
        self.logger = logging.LoggerAdapter(
            logging.getLogger(__name__), {"server_name": server.server_name}
        )

    async def set_player_permission(
        self, xuid: str, permission_level: str, player_name: Optional[str] = None
    ) -> None:
        """Sets the permission level for a player asynchronously."""
        async with self.server.get_file_lock(self.server.paths.permissions_json_path):
            if not await aiofiles.ospath.isdir(self.server.paths.server_dir):
                raise AppFileNotFoundError(
                    self.server.paths.server_dir, "Server directory"
                )
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
            self.logger.debug(
                "Server '%s': Setting permission for XUID '%s' to '%s'.",
                self.server.server_name,
                xuid,
                perm_level_lower,
            )
            permissions_list: List[Dict[str, Any]] = []
            if await aiofiles.ospath.isfile(self.server.paths.permissions_json_path):
                try:
                    loaded_data = await load_json(
                        self.server.paths.permissions_json_path
                    )
                    if isinstance(loaded_data, list):
                        permissions_list = [
                            entry.model_dump(mode="json", exclude_unset=True)
                            for entry in PERMISSIONS.validate_python(loaded_data)
                        ]
                    elif loaded_data:
                        self.logger.warning(
                            "Permissions file '%s' is not a list. Overwriting.",
                            self.server.paths.permissions_json_path,
                        )
                except ValueError as e:
                    self.logger.warning(
                        "Invalid JSON in permissions '%s'. Overwriting. Error: %s",
                        self.server.paths.permissions_json_path,
                        e,
                    )
                except OSError as e:
                    raise FileOperationError(
                        f"Failed to read permissions '{self.server.paths.permissions_json_path}': {e}"
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
                    {
                        "permission": perm_level_lower,
                        "xuid": xuid,
                        "name": effective_name,
                    }
                )
                modified = True
            if modified:
                try:
                    lock = self.server.get_file_lock(
                        self.server.paths.permissions_json_path
                    )
                    async with lock:
                        await save_json(
                            permissions_list,
                            self.server.paths.permissions_json_path,
                            indent=4,
                        )
                    self.logger.info(
                        "Successfully updated permissions for XUID '%s' for '%s'.",
                        xuid,
                        self.server.server_name,
                    )
                except OSError as e:
                    raise FileOperationError(
                        f"Failed to write permissions '{self.server.paths.permissions_json_path}': {e}"
                    ) from e
            else:
                self.logger.debug(
                    "No changes needed for XUID '%s' permissions for '%s'.",
                    xuid,
                    self.server.server_name,
                )

    async def get_formatted_permissions(self, storage: Any) -> List[Dict[str, Any]]:
        """Retrieves permissions and maps XUIDs to known player names asynchronously."""
        if not await aiofiles.ospath.isdir(self.server.paths.server_dir):
            raise AppFileNotFoundError(self.server.paths.server_dir, "Server directory")
        if not await aiofiles.ospath.isfile(self.server.paths.permissions_json_path):
            raise AppFileNotFoundError(
                self.server.paths.permissions_json_path, "Permissions file"
            )
        self.logger.debug(
            "Server '%s': Reading and processing permissions from %s",
            self.server.server_name,
            self.server.paths.permissions_json_path,
        )
        raw_permissions: List[Dict[str, Any]] = []
        try:
            loaded_data = await load_json(self.server.paths.permissions_json_path)
            if isinstance(loaded_data, list):
                raw_permissions = [
                    entry.model_dump(mode="json", exclude_unset=True)
                    for entry in PERMISSIONS.validate_python(loaded_data)
                ]
            elif loaded_data:
                raise ConfigParseError("Permissions file content is not a list.")
        except ValueError as e:
            raise ConfigParseError(f"Invalid JSON in permissions file: {e}") from e
        except OSError as e:
            raise FileOperationError(
                f"OSError reading permissions file '{self.server.paths.permissions_json_path}': {e}"
            ) from e
        try:
            known_players = await get_known_players(storage)
            player_map = {p["xuid"]: p["name"] for p in known_players}
        except Exception as e:
            log_operation_error(
                self.logger,
                "Error retrieving known players from database: %s. Will use XUIDs as names where needed.",
                e,
                error=e,
            )
            player_map = {}
        processed_list: List[Dict[str, Any]] = []
        for entry in raw_permissions:
            if isinstance(entry, dict) and "xuid" in entry and ("permission" in entry):
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
                    "Skipping malformed entry in '%s': %s",
                    self.server.paths.permissions_json_path,
                    entry,
                )
        processed_list.sort(key=lambda p: str(p.get("name", "")).lower())
        return processed_list
