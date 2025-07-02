# bedrock_server_manager/core/server/config_management_mixin.py
"""
Provides the :class:`.ServerConfigManagementMixin` for the
:class:`~.core.bedrock_server.BedrockServer` class.

This mixin centralizes the logic for interacting with key server-specific
configuration files:
    - ``allowlist.json``: For managing players who are allowed to join the server.
    - ``permissions.json``: For defining operator levels and permissions for players.
    - ``server.properties``: The main configuration file for Bedrock server settings.

It offers methods to read, parse, modify, and write these files in a structured
manner, abstracting direct file I/O and providing error handling for common
issues like file not found or parsing errors.
"""
import os
import json
import logging
from typing import List, Dict, Any, Optional

# Local application imports.
from bedrock_server_manager.core.server.base_server_mixin import BedrockServerBaseMixin
from bedrock_server_manager.error import (
    MissingArgumentError,
    FileOperationError,
    UserInputError,
    AppFileNotFoundError,
    ConfigParseError,
)


class ServerConfigManagementMixin(BedrockServerBaseMixin):
    """Provides methods to manage server-specific configuration files.

    This mixin extends :class:`.BedrockServerBaseMixin` and is responsible for
    all interactions with the primary configuration files of a Bedrock server:
    ``allowlist.json``, ``permissions.json``, and ``server.properties``.
    It offers a structured interface for reading, writing, and modifying these
    critical files.

    It relies on attributes initialized by :class:`.BedrockServerBaseMixin`
    (e.g., `server_dir`, `logger`) for path construction and logging.

    Properties:
        allowlist_json_path (str): Path to the ``allowlist.json`` file.
        permissions_json_path (str): Path to the ``permissions.json`` file.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initializes the ServerConfigManagementMixin.

        Calls ``super().__init__(*args, **kwargs)`` to participate in cooperative
        multiple inheritance. It depends on attributes initialized by
        :class:`.BedrockServerBaseMixin`, such as `server_dir` (to locate
        configuration files) and `logger`.

        Args:
            *args (Any): Variable length argument list passed to `super()`.
            **kwargs (Any): Arbitrary keyword arguments passed to `super()`.
        """
        super().__init__(*args, **kwargs)
        # Attributes from BedrockServerBaseMixin (e.g., self.server_dir, self.logger) are available.

    # --- ALLOWLIST METHODS ---
    @property
    def allowlist_json_path(self) -> str:
        """str: The absolute path to this server's ``allowlist.json`` file.

        Constructed using :attr:`~.BedrockServerBaseMixin.server_dir`.
        """
        return os.path.join(self.server_dir, "allowlist.json")

    def get_allowlist(self) -> List[Dict[str, Any]]:
        """Loads and returns the content of the server's ``allowlist.json`` file.

        The ``allowlist.json`` file typically contains a list of player objects,
        where each object has keys like "name", "xuid", and "ignoresPlayerLimit".

        Returns:
            List[Dict[str, Any]]: A list of player dictionaries parsed from the
            ``allowlist.json`` file. Returns an empty list if the file does not
            exist, is empty, or if its content is not a valid JSON list.

        Raises:
            AppFileNotFoundError: If the server's installation directory
                (:attr:`~.BedrockServerBaseMixin.server_dir`) does not exist.
            ConfigParseError: If the ``allowlist.json`` file contains malformed JSON
                that cannot be parsed.
            FileOperationError: If an OS-level error occurs while trying to read
                the file (e.g., permission issues).
        """
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
        """Adds one or more players to the server's ``allowlist.json`` file.

        This method loads the current allowlist, then iterates through the
        `players_to_add`. For each player, it checks if a player with the same
        name (case-insensitive) already exists in the allowlist. If not, the new
        player entry is added. The `ignoresPlayerLimit` key is defaulted to `False`
        if not present in the input player dictionary, conforming to Bedrock standards.
        Finally, the updated allowlist is written back to ``allowlist.json``.

        Args:
            players_to_add (List[Dict[str, Any]]): A list of player dictionaries
                to add. Each dictionary must contain a "name" key (str). It can
                optionally include "xuid" (str) and "ignoresPlayerLimit" (bool).
                Example: ``[{"name": "Player1", "xuid": "12345", "ignoresPlayerLimit": False}]``

        Returns:
            int: The number of players that were actually added to the allowlist
            (i.e., those not already present).

        Raises:
            TypeError: If `players_to_add` is not a list.
            AppFileNotFoundError: If the server's installation directory
                (:attr:`~.BedrockServerBaseMixin.server_dir`) does not exist.
            ConfigParseError: If the existing ``allowlist.json`` is malformed
                (from :meth:`.get_allowlist`).
            FileOperationError: If reading from or writing to ``allowlist.json`` fails.
        """
        if not isinstance(players_to_add, list):
            raise TypeError("Input 'players_to_add' must be a list of dictionaries.")
        if not os.path.isdir(self.server_dir):
            raise AppFileNotFoundError(self.server_dir, "Server directory")

        self.logger.info(
            f"Server '{self.server_name}': Adding {len(players_to_add)} player(s) to allowlist."
        )

        current_allowlist = self.get_allowlist()
        # Create a set of existing names for efficient duplicate checking.
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
                # Ensure the 'ignoresPlayerLimit' key exists, defaulting to False as per Bedrock standard.
                if "ignoresPlayerLimit" not in player_entry:
                    player_entry["ignoresPlayerLimit"] = False
                current_allowlist.append(player_entry)
                # Add the new name to our set to prevent duplicates within the same batch.
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
        """Removes a player from the server's ``allowlist.json`` by their gamertag.

        This method loads the current allowlist, filters out the player whose
        name matches `player_name_to_remove` (case-insensitively), and then
        writes the modified allowlist back to the file.

        Args:
            player_name_to_remove (str): The gamertag of the player to remove
                from the allowlist.

        Returns:
            bool: ``True`` if a player with the given name was found and removed,
            ``False`` otherwise (e.g., if the player was not on the allowlist).

        Raises:
            MissingArgumentError: If `player_name_to_remove` is empty or not a string.
            AppFileNotFoundError: If the server's installation directory does not exist.
            ConfigParseError: If the existing ``allowlist.json`` is malformed.
            FileOperationError: If reading from or writing to ``allowlist.json`` fails.
        """
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

        # Rebuild the list, excluding the player to be removed.
        updated_allowlist = [
            p
            for p in current_allowlist
            if not (
                isinstance(p, dict)
                and p.get("name", "").lower() == name_lower_to_remove
            )
        ]

        # If the list length changed, a player was removed.
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

    # --- PERMISSIONS.JSON METHODS ---
    @property
    def permissions_json_path(self) -> str:
        """str: The absolute path to this server's ``permissions.json`` file.

        Constructed using :attr:`~.BedrockServerBaseMixin.server_dir`.
        """
        return os.path.join(self.server_dir, "permissions.json")

    def set_player_permission(
        self, xuid: str, permission_level: str, player_name: Optional[str] = None
    ) -> None:
        """Sets or updates a player's permission level in ``permissions.json``.

        This method manages entries in the server's ``permissions.json`` file.
        If a player with the given `xuid` already exists in the file, their
        permission level is updated to `permission_level`. If a `player_name` is
        provided and differs from an existing entry for that XUID, the name is
        also updated. If the player (by XUID) does not exist, a new entry is
        created with the specified `xuid`, `permission_level`, and `player_name`
        (or XUID if name is not provided).

        Valid permission levels are "operator", "member", and "visitor".

        Args:
            xuid (str): The player's Xbox User ID (XUID).
            permission_level (str): The permission level to set. Must be one of
                "operator", "member", or "visitor" (case-insensitive).
            player_name (Optional[str], optional): The player's gamertag.
                If provided, it will be included in the permissions entry for
                reference. Defaults to ``None`` (in which case XUID might be used
                as name for new entries).

        Raises:
            AppFileNotFoundError: If the server's installation directory does not exist.
            MissingArgumentError: If `xuid` or `permission_level` are empty or not strings.
            UserInputError: If `permission_level` is not one of the valid options.
            FileOperationError: If reading from or writing to ``permissions.json`` fails.
            ConfigParseError: If the existing ``permissions.json`` is malformed.
        """
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

        # Safely load the existing permissions list.
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
        # Find and update the existing entry if it exists.
        for entry in permissions_list:
            if isinstance(entry, dict) and entry.get("xuid") == xuid:
                entry_found = True
                if entry.get("permission") != perm_level_lower:
                    entry["permission"] = perm_level_lower
                    modified = True
                # Also update the name if a new one is provided.
                if player_name and entry.get("name") != player_name:
                    entry["name"] = player_name
                    modified = True
                break

        # If no entry was found, create a new one.
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
        """Reads ``permissions.json``, enriches entries with player names, and sorts them.

        This method loads the raw data from the server's ``permissions.json`` file.
        For each permission entry (which typically contains "xuid" and "permission"),
        it attempts to find the corresponding player's gamertag using the provided
        `player_xuid_to_name_map`. If a name is found, it's added to the entry;
        otherwise, a default placeholder like "Unknown (XUID: <xuid>)" is used.

        The resulting list of enriched permission entries is then sorted alphabetically
        by player name (case-insensitive).

        Args:
            player_xuid_to_name_map (Dict[str, str]): A dictionary mapping player
                XUIDs (str) to their last known gamertags (str). This is used to
                populate the "name" field in the returned permission entries.

        Returns:
            List[Dict[str, Any]]: A sorted list of player permission dictionaries.

            Each dictionary in the list will contain:

                - "xuid" (str): The player's XUID.
                - "name" (str): The player's gamertag (from the map or a default).
                - "permission_level" (str): The player's permission level (e.g., "operator").

            Returns an empty list if ``permissions.json`` does not exist, is empty,
            or contains no valid entries.

        Raises:
            AppFileNotFoundError: If the server's installation directory or the
                ``permissions.json`` file itself does not exist.
            ConfigParseError: If the ``permissions.json`` file contains malformed
                JSON or its top-level structure is not a list.
            FileOperationError: If an OS-level error occurs while reading the file.
        """
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
                # Use the provided map to find the player's name, or fall back to a default.
                name = player_xuid_to_name_map.get(xuid, f"Unknown (XUID: {xuid})")
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

    # --- SERVER.PROPERTIES METHODS ---

    def set_server_property(self, property_key: str, property_value: Any) -> None:
        """Modifies or adds a property in the server's ``server.properties`` file.

        This method reads the entire ``server.properties`` file line by line.
        If a line starting with `property_key=` is found, it's replaced with the
        new `property_key=property_value`. If the key is not found, the new
        property line is appended to the end of the file. Comments and blank
        lines are preserved. Duplicate entries for the same key (if any) will
        result in the first being updated and subsequent ones being commented out.

        The `property_value` is converted to a string before writing.

        Args:
            property_key (str): The property key to set (e.g., "level-name",
                "max-players").
            property_value (Any): The value to set for the property. It will be
                converted to a string.

        Raises:
            MissingArgumentError: If `property_key` is empty or not a string.
            UserInputError: If `property_value`, when converted to a string,
                contains invalid control characters (excluding tab).
            AppFileNotFoundError: If the ``server.properties`` file (at
                :attr:`.ServerStateMixin.server_properties_path`) does not exist.
            FileOperationError: If reading from or writing to ``server.properties`` fails.
        """
        if not isinstance(property_key, str) or not property_key:
            raise MissingArgumentError(
                "Property key cannot be empty and must be a string."
            )

        str_value = str(property_value)
        # Check for invalid control characters that can corrupt the properties file.
        if any(ord(c) < 32 for c in str_value if c != "\t"):
            raise UserInputError(
                f"Property value for '{property_key}' contains invalid control characters."
            )

        if not os.path.isfile(self.server_properties_path):
            raise AppFileNotFoundError(
                self.server_properties_path, "Server properties file"
            )

        self.logger.debug(
            f"Server '{self.server_name}': Setting property '{property_key}' to '{str_value}' in {self.server_properties_path}"
        )

        try:
            with open(self.server_properties_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except OSError as e:
            raise FileOperationError(
                f"Failed to read '{self.server_properties_path}': {e}"
            ) from e

        output_lines = []
        property_found_and_set = False
        new_property_line = f"{property_key}={str_value}\n"

        for line_content in lines:
            stripped_line = line_content.strip()
            # Preserve comments and blank lines.
            if not stripped_line or stripped_line.startswith("#"):
                output_lines.append(line_content)
                continue

            # If the line starts with the key we're looking for, replace it.
            if stripped_line.startswith(property_key + "="):
                # Only replace the first occurrence to handle malformed files.
                if not property_found_and_set:
                    output_lines.append(new_property_line)
                    property_found_and_set = True
                else:
                    # Comment out any duplicate entries.
                    output_lines.append("# DUPLICATE IGNORED: " + line_content)
            else:
                output_lines.append(line_content)

        # If the property was not found in the file, add it to the end.
        if not property_found_and_set:
            if output_lines and not output_lines[-1].endswith("\n"):
                output_lines[-1] += "\n"
            output_lines.append(new_property_line)

        try:
            with open(self.server_properties_path, "w", encoding="utf-8") as f:
                f.writelines(output_lines)
            self.logger.info(
                f"Successfully set property '{property_key}' for '{self.server_name}'."
            )
        except OSError as e:
            raise FileOperationError(
                f"Failed to write '{self.server_properties_path}': {e}"
            ) from e

    def get_server_properties(self) -> Dict[str, str]:
        """Reads and parses the server's ``server.properties`` file into a dictionary.

        Each line in the format ``key=value`` is parsed. Lines starting with ``#``
        (comments) and blank lines are ignored. If a line is malformed (e.g.,
        does not contain an "="), a warning is logged, and the line is skipped.

        Returns:
            Dict[str, str]: A dictionary where keys are property names and values
            are their corresponding string values from the ``server.properties`` file.
            An empty dictionary is returned if the file is empty or contains no
            valid properties.

        Raises:
            AppFileNotFoundError: If the ``server.properties`` file (at
                :attr:`.ServerStateMixin.server_properties_path`) does not exist.
            ConfigParseError: If an ``OSError`` occurs while trying to read the file
                (e.g., permission issues), effectively making it unparseable.
        """
        if not os.path.isfile(self.server_properties_path):
            raise AppFileNotFoundError(
                self.server_properties_path, "Server properties file"
            )

        self.logger.debug(
            f"Server '{self.server_name}': Parsing {self.server_properties_path}"
        )
        properties: Dict[str, str] = {}
        try:
            with open(self.server_properties_path, "r", encoding="utf-8") as f:
                for line_num, line_content in enumerate(f, 1):
                    line = line_content.strip()
                    # Ignore comments and empty lines.
                    if not line or line.startswith("#"):
                        continue
                    parts = line.split("=", 1)
                    if len(parts) == 2 and parts[0].strip():
                        properties[parts[0].strip()] = parts[1].strip()
                    else:
                        self.logger.warning(
                            f"Skipping malformed line {line_num} in '{self.server_properties_path}': \"{line}\""
                        )
        except OSError as e:
            raise ConfigParseError(
                f"Failed to read '{self.server_properties_path}': {e}"
            ) from e

        return properties

    def get_server_property(
        self, property_key: str, default: Optional[Any] = None
    ) -> Optional[Any]:
        """Retrieves a specific property value from ``server.properties``.

        This method first calls :meth:`.get_server_properties` to parse the entire
        file, then returns the value associated with `property_key`. If the
        key is not found or if the ``server.properties`` file itself does not
        exist (or is unreadable), the specified `default` value is returned.

        Args:
            property_key (str): The key of the property to retrieve (e.g., "level-name").
            default (Optional[Any], optional): The value to return if the key is
                not found or if the properties file cannot be accessed.
                Defaults to ``None``.

        Returns:
            Optional[Any]: The value of the property (typically a string), or the
            `default` value if the property is not found or an error occurs
            during file access/parsing.
        """
        if not isinstance(property_key, str) or not property_key:
            self.logger.warning(
                f"get_server_property called with invalid key: {property_key}. Returning default."
            )
            return default
        try:
            props = self.get_server_properties()
            return props.get(property_key, default)
        except AppFileNotFoundError:
            return default
