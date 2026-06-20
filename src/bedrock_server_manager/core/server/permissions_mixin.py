import json
import os
from typing import Any, Dict, List, Optional

from ...error import (
    AppFileNotFoundError,
    ConfigParseError,
    FileOperationError,
    MissingArgumentError,
    UserInputError,
)
from .base_server_mixin import BedrockServerBaseMixin


class ServerPermissionsMixin(BedrockServerBaseMixin):
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
