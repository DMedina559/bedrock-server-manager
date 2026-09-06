import asyncio
import json
import os
import typing
from typing import Any, Dict, List, Optional

import aiofiles
import aiofiles.ospath

from ...core.player import async_get_known_players
from ...error import (
    AppFileNotFoundError,
    ConfigParseError,
    FileOperationError,
    MissingArgumentError,
    UserInputError,
)
from .base_server_mixin import BedrockServerBaseMixin


class ServerPermissionsMixin(BedrockServerBaseMixin):
    """Provides methods for managing the permissions.json configuration."""

    @typing.no_type_check
    async def async_set_player_permission(  # noqa: C901
        self, target_player_xuid: str, permission_level: str
    ) -> bool:  # type: ignore
        """Sets the permission level for a player asynchronously."""

        self.logger.debug(
            f"Setting permission for XUID '{target_player_xuid}' to '{permission_level}' on '{self.server_name}' asynchronously."
        )

        valid_levels = ["visitor", "member", "operator"]
        if permission_level not in valid_levels:
            raise UserInputError(
                f"Invalid permission level '{permission_level}'. Must be one of {valid_levels}."
            )

        if not target_player_xuid or not isinstance(target_player_xuid, str):
            raise UserInputError(
                "Target player XUID must be a valid, non-empty string."
            )

        if not await aiofiles.ospath.isfile(self.permissions_path):
            self.logger.warning(
                f"Permissions file not found at '{self.permissions_path}' for '{self.server_name}'. A new one will be created."
            )
            permissions_data = []
        else:
            try:
                async with aiofiles.open(
                    self.permissions_path, "r", encoding="utf-8"
                ) as f:
                    content = await f.read()
                    permissions_data = json.loads(content)
            except json.JSONDecodeError as e:
                self.logger.error(
                    f"JSON decode error in {self.permissions_path}: {e}. Creating a fresh permissions list."
                )
                permissions_data = []
            except Exception as e:
                self.logger.error(f"Error reading {self.permissions_path}: {e}")
                return False

        updated = False
        for entry in permissions_data:
            if entry.get("xuid") == target_player_xuid:
                if entry.get("permission") != permission_level:
                    entry["permission"] = permission_level
                    updated = True
                else:
                    self.logger.debug(
                        f"Player XUID '{target_player_xuid}' already has permission '{permission_level}'. No changes needed."
                    )
                    return True
                break
        else:
            permissions_data.append(
                {"xuid": target_player_xuid, "permission": permission_level}
            )
            updated = True

        if updated:
            try:
                async with aiofiles.open(
                    self.permissions_path, "w", encoding="utf-8"
                ) as f:
                    content = json.dumps(permissions_data, indent=4)
                    await f.write(content)
                self.logger.info(
                    f"Successfully set permission for '{target_player_xuid}' to '{permission_level}'."
                )

                if hasattr(self, "async_is_running"):
                    is_running = await self.async_is_running()
                else:

                    is_running = await asyncio.to_thread(self.is_running)

                if is_running:
                    if hasattr(self, "async_send_command"):
                        await self.async_send_command("permission reload")
                    else:

                        await asyncio.to_thread(self.send_command, "permission reload")
                    self.logger.info(
                        f"Reloaded permissions for running server '{self.server_name}'."
                    )

                return True
            except Exception as e:
                self.logger.error(f"Failed to write to {self.permissions_path}: {e}")
                return False

        return True

    @typing.no_type_check
    async def async_get_formatted_permissions(
        self, db_session_manager
    ) -> List[Dict[str, str]]:  # type: ignore
        """Retrieves permissions and maps XUIDs to known player names asynchronously."""

        if not await aiofiles.ospath.isfile(self.permissions_path):
            self.logger.debug(
                f"Permissions file not found at '{self.permissions_path}'. Returning empty list."
            )
            return []

        try:
            async with aiofiles.open(self.permissions_path, "r", encoding="utf-8") as f:
                content = await f.read()
                permissions_data = json.loads(content)
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON decode error in {self.permissions_path}: {e}")
            return []
        except Exception as e:
            self.logger.error(f"Error reading {self.permissions_path}: {e}")
            return []

        try:
            known_players = await async_get_known_players(db_session_manager)
            player_map = {p["xuid"]: p["name"] for p in known_players}
        except Exception as e:
            self.logger.error(
                f"Error retrieving known players from database: {e}. Will use XUIDs as names where needed."
            )
            player_map = {}

        formatted_list = []
        for p in permissions_data:
            xuid = p.get("xuid")
            if xuid:
                player_name = player_map.get(xuid, "Unknown Player")
                formatted_list.append(
                    {
                        "xuid": xuid,
                        "permission": p.get("permission", "unknown"),
                        "player_name": player_name,
                    }
                )
        return formatted_list

    def set_player_permission(  # noqa: C901
        self, xuid: str, permission_level: str, player_name: Optional[str] = None
    ) -> None:
        if not os.path.isdir(
            self.server_dir
        ):  # Ensures server_dir exists before trying to write to it
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
        if os.path.isfile(self.permissions_json_path):
            try:
                with open(self.permissions_json_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    if content.strip():
                        loaded_data = json.loads(content)
                        if isinstance(loaded_data, list):
                            permissions_list = loaded_data
                        else:
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
                with open(self.permissions_json_path, "w", encoding="utf-8") as f:
                    json.dump(permissions_list, f, indent=4, sort_keys=True)
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

    def get_formatted_permissions(
        self, player_xuid_to_name_map: Dict[str, str]
    ) -> List[Dict[str, Any]]:
        if not os.path.isdir(self.server_dir):
            raise AppFileNotFoundError(self.server_dir, "Server directory")
        if not os.path.isfile(self.permissions_json_path):
            raise AppFileNotFoundError(self.permissions_json_path, "Permissions file")

        self.logger.debug(
            f"Server '{self.server_name}': Reading and processing permissions from {self.permissions_json_path}"
        )

        raw_permissions: List[Dict[str, Any]] = []
        try:
            with open(self.permissions_json_path, "r", encoding="utf-8") as f:
                content = f.read()
                if content.strip():
                    loaded_data = json.loads(content)
                    if isinstance(loaded_data, list):
                        raw_permissions = loaded_data
                    else:
                        raise ConfigParseError(
                            "Permissions file content is not a list."
                        )
        except ValueError as e:
            raise ConfigParseError(f"Invalid JSON in permissions file: {e}") from e
        except OSError as e:
            raise FileOperationError(
                f"OSError reading permissions file '{self.permissions_json_path}': {e}"
            ) from e

        processed_list: List[Dict[str, Any]] = []
        for entry in raw_permissions:
            if isinstance(entry, dict) and "xuid" in entry and "permission" in entry:
                xuid = str(entry["xuid"])
                name = player_xuid_to_name_map.get(
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

        processed_list.sort(key=lambda p: p.get("name", "").lower())
        return processed_list
