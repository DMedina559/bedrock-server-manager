# bedrock_server_manager/api/server_install_config.py
"""Provides API functions for server installation, updates, and detailed configuration.

This module serves as an interface for managing the setup and fine-grained
configuration of Bedrock server instances. It primarily orchestrates calls to the
:class:`~bedrock_server_manager.core.bedrock_server.BedrockServer` class to
handle operations related to:

- Server software lifecycle:
    - :func:`~.install_new_server`: Installation of new server instances.
    - :func:`~.update_server`: Updating existing servers to target versions.
- Configuration file management:
    - ``server.properties``: Reading and modifying server game settings via
      :func:`~.get_server_properties_api` and :func:`~.modify_server_properties`.
    - ``allowlist.json``: Managing the player allowlist through functions like
      :func:`~.add_players_to_allowlist_api`, :func:`~.get_server_allowlist_api`,
      and :func:`~.remove_players_from_allowlist`.
    - ``permissions.json``: Configuring player operator levels via
      :func:`~.configure_player_permission` and :func:`~.get_server_permissions_api`.
- Validation:
    - :func:`~.validate_server_property_value`: A helper to check server property values.

Functions in this module typically return structured dictionary responses suitable for
use by web routes or CLI commands and integrate with the plugin system for extensibility.
"""
import os
import logging
import re
from typing import Dict, List, Optional, Any

# Plugin system imports to bridge API functionality.
from bedrock_server_manager import plugin_manager
from bedrock_server_manager.plugins.api_bridge import plugin_method

# Local application imports.
from bedrock_server_manager.core.bedrock_server import BedrockServer
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.api import player as player_api
from bedrock_server_manager.api.utils import (
    server_lifecycle_manager,
    validate_server_name_format,
)
from bedrock_server_manager.error import (
    BSMError,
    InvalidServerNameError,
    FileOperationError,
    MissingArgumentError,
    UserInputError,
    AppFileNotFoundError,
)

logger = logging.getLogger(__name__)


# --- Allowlist ---
@plugin_method("add_players_to_allowlist_api")
def add_players_to_allowlist_api(
    server_name: str, new_players_data: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Adds new players to the allowlist for a specific server.

    This function updates the server's ``allowlist.json`` file by calling
    :meth:`~.core.bedrock_server.BedrockServer.add_to_allowlist`.
    If the server is running, the underlying BedrockServer method typically
    attempts to reload the allowlist via a server command.
    Triggers ``before_allowlist_change`` and ``after_allowlist_change`` plugin events.

    Args:
        server_name (str): The name of the server to modify.
        new_players_data (List[Dict[str, Any]]): A list of player dictionaries
            to add. Each dictionary **must** contain a "name" key (str).
            It can optionally include "xuid" (str) and "ignoresPlayerLimit" (bool,
            defaults to ``False`` if not provided).

    Returns:
        Dict[str, Any]: A dictionary with the operation result.
        On success: ``{"status": "success", "message": "Successfully added <n> new players...", "added_count": <n>}``
        On error: ``{"status": "error", "message": "<error_message>"}``

    Raises:
        MissingArgumentError: If `server_name` is empty.
        TypeError: If `new_players_data` is not a list.
        AppFileNotFoundError: If the server's installation directory does not exist.
        ConfigParseError: If the existing ``allowlist.json`` is malformed.
        FileOperationError: If reading/writing ``allowlist.json`` fails.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    if not isinstance(new_players_data, list):
        return {
            "status": "error",
            "message": "Invalid input: new_players_data must be a list.",
        }

    plugin_manager.trigger_event(
        "before_allowlist_change",
        server_name=server_name,
        players_to_add=new_players_data,
        players_to_remove=[],
    )

    logger.info(
        f"API: Adding {len(new_players_data)} player(s) to allowlist for '{server_name}'."
    )
    result = {}
    try:
        server = BedrockServer(server_name)
        added_count = server.add_to_allowlist(new_players_data)

        result = {
            "status": "success",
            "message": f"Successfully added {added_count} new players to the allowlist.",
            "added_count": added_count,
        }

    except (FileOperationError, TypeError) as e:
        logger.error(
            f"API: Failed to update allowlist for '{server_name}': {e}", exc_info=True
        )
        result = {"status": "error", "message": f"Failed to update allowlist: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error updating allowlist for '{server_name}': {e}",
            exc_info=True,
        )
        result = {
            "status": "error",
            "message": f"Unexpected error updating allowlist: {e}",
        }
    finally:
        plugin_manager.trigger_event(
            "after_allowlist_change", server_name=server_name, result=result
        )

    return result


@plugin_method("get_server_allowlist_api")
def get_server_allowlist_api(server_name: str) -> Dict[str, Any]:
    """Retrieves the allowlist for a specific server.

    Calls :meth:`~.core.bedrock_server.BedrockServer.get_allowlist`
    to read and parse the server's ``allowlist.json`` file.

    Args:
        server_name (str): The name of the server.

    Returns:
        Dict[str, Any]: A dictionary with the operation result.
        On success: ``{"status": "success", "players": List[Dict[str, Any]]}``
        where `players` is the list of entries from ``allowlist.json``.
        Returns an empty list for `players` if the file doesn't exist or is empty.
        On error: ``{"status": "error", "message": "<error_message>"}``

    Raises:
        MissingArgumentError: If `server_name` is empty.
        AppFileNotFoundError: If the server's installation directory does not exist.
        ConfigParseError: If ``allowlist.json`` is malformed.
        FileOperationError: If reading ``allowlist.json`` fails.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")

    try:
        server = BedrockServer(server_name)
        players = server.get_allowlist()
        return {"status": "success", "players": players}
    except BSMError as e:
        logger.error(
            f"API: Failed to access allowlist for '{server_name}': {e}", exc_info=True
        )
        return {"status": "error", "message": f"Failed to access allowlist: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error reading allowlist for '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Unexpected error reading allowlist: {e}",
        }


@plugin_method("remove_players_from_allowlist")
def remove_players_from_allowlist(
    server_name: str, player_names: List[str]
) -> Dict[str, Any]:
    """Removes one or more players from the server's allowlist by name.

    This function iterates through the provided `player_names` and calls
    :meth:`~.core.bedrock_server.BedrockServer.remove_from_allowlist` for each.
    Triggers ``before_allowlist_change`` and ``after_allowlist_change`` plugin events.

    Args:
        server_name (str): The name of the server to modify.
        player_names (List[str]): A list of player gamertags to remove.
            Case-insensitive matching is performed for removal.

    Returns:
        Dict[str, Any]: A dictionary with the operation result.
        On success: ``{"status": "success", "message": "Allowlist update process completed.", "details": {"removed": List[str], "not_found": List[str]}}``
        If `player_names` is empty: ``{"status": "success", "message": "No players specified...", "details": {"removed": [], "not_found": []}}``
        On error: ``{"status": "error", "message": "<error_message>"}``

    Raises:
        MissingArgumentError: If `server_name` is empty.
        AppFileNotFoundError: If the server's installation directory does not exist.
        ConfigParseError: If the existing ``allowlist.json`` is malformed.
        FileOperationError: If reading/writing ``allowlist.json`` fails during the process.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")

    plugin_manager.trigger_event(
        "before_allowlist_change",
        server_name=server_name,
        players_to_add=[],
        players_to_remove=player_names,
    )

    result = {}
    try:
        if not player_names:
            return {
                "status": "success",
                "message": "No players specified for removal.",
                "details": {"removed": [], "not_found": []},
            }

        server = BedrockServer(server_name)
        removed_players, not_found_players = [], []

        # Iterate and remove each player, tracking success and failure.
        for player in player_names:
            if server.remove_from_allowlist(player):
                removed_players.append(player)
            else:
                not_found_players.append(player)

        result = {
            "status": "success",
            "message": "Allowlist update process completed.",
            "details": {"removed": removed_players, "not_found": not_found_players},
        }

    except BSMError as e:
        logger.error(
            f"API: Failed to remove players from allowlist for '{server_name}': {e}",
            exc_info=True,
        )
        result = {
            "status": "error",
            "message": f"Failed to process allowlist removal: {e}",
        }
    except Exception as e:
        logger.error(
            f"API: Unexpected error removing players for '{server_name}': {e}",
            exc_info=True,
        )
        result = {"status": "error", "message": f"Unexpected error: {e}"}
    finally:
        plugin_manager.trigger_event(
            "after_allowlist_change", server_name=server_name, result=result
        )

    return result


# --- Player Permissions ---
@plugin_method("configure_player_permission")
def configure_player_permission(
    server_name: str, xuid: str, player_name: Optional[str], permission: str
) -> Dict[str, str]:
    """Sets a player's permission level in permissions.json.

    This function calls
    :meth:`~.core.bedrock_server.BedrockServer.set_player_permission`
    to update the server's ``permissions.json`` file.
    Valid permission levels are "operator", "member", and "visitor".
    Triggers ``before_permission_change`` and ``after_permission_change`` plugin events.

    Args:
        server_name (str): The name of the server.
        xuid (str): The player's XUID. Cannot be empty.
        player_name (Optional[str]): The player's gamertag. Included in the
            ``permissions.json`` entry for reference if provided.
        permission (str): The permission level to set (e.g., 'member', 'operator',
            'visitor'). Case-insensitive. Cannot be empty.

    Returns:
        Dict[str, str]: A dictionary with the operation result.
        On success: ``{"status": "success", "message": "Permission for XUID '<xuid>' set to '<perm>'."}``
        On error: ``{"status": "error", "message": "<error_message>"}``

    Raises:
        InvalidServerNameError: If `server_name` is empty.
        MissingArgumentError: If `xuid` or `permission` are empty.
        UserInputError: If `permission` is not a valid level.
        AppFileNotFoundError: If server directory or ``permissions.json`` (if expected) are missing.
        FileOperationError: If reading/writing ``permissions.json`` fails.
        ConfigParseError: If existing ``permissions.json`` is malformed.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    plugin_manager.trigger_event(
        "before_permission_change",
        server_name=server_name,
        xuid=xuid,
        permission=permission,
    )

    result = {}
    try:
        server = BedrockServer(server_name)
        server.set_player_permission(xuid, permission, player_name)

        result = {
            "status": "success",
            "message": f"Permission for XUID '{xuid}' set to '{permission.lower()}'.",
        }

    except BSMError as e:
        logger.error(
            f"API: Failed to configure permission for '{server_name}': {e}",
            exc_info=True,
        )
        result = {"status": "error", "message": f"Failed to configure permission: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error configuring permission for '{server_name}': {e}",
            exc_info=True,
        )
        result = {"status": "error", "message": f"Unexpected error: {e}"}
    finally:
        plugin_manager.trigger_event(
            "after_permission_change", server_name=server_name, xuid=xuid, result=result
        )

    return result


@plugin_method("get_server_permissions_api")
def get_server_permissions_api(server_name: str) -> Dict[str, Any]:
    """Retrieves processed permissions data for a server.

    This function reads the server's ``permissions.json`` file via
    :meth:`~.core.bedrock_server.BedrockServer.get_formatted_permissions`.
    To enrich the data, it first fetches a global XUID-to-name mapping using
    :func:`~bedrock_server_manager.api.player.get_all_known_players_api`.
    The resulting list of permissions is sorted by player name.

    Args:
        server_name (str): The name of the server.

    Returns:
        Dict[str, Any]: A dictionary with the operation result.
        On success: ``{"status": "success", "data": {"permissions": List[Dict[str, Any]]}}``
        where each dict in `permissions` contains "xuid", "name", and "permission_level".
        If ``permissions.json`` doesn't exist, `permissions` will be an empty list.
        On error: ``{"status": "error", "message": "<error_message>"}``

    Raises:
        MissingArgumentError: If `server_name` is empty.
        AppFileNotFoundError: If server directory is missing (but not if only ``permissions.json`` is missing).
        ConfigParseError: If ``permissions.json`` is malformed.
        FileOperationError: If reading ``permissions.json`` fails.
    """
    if not server_name:
        return {"status": "error", "message": "Server name cannot be empty."}

    try:
        server = BedrockServer(server_name)
        player_name_map: Dict[str, str] = {}

        # Fetch global player data to create a XUID -> Name mapping.
        players_response = player_api.get_all_known_players_api()
        if players_response.get("status") == "success":
            for p_data in players_response.get("players", []):
                if p_data.get("xuid") and p_data.get("name"):
                    player_name_map[str(p_data["xuid"])] = str(p_data["name"])

        permissions = server.get_formatted_permissions(player_name_map)
        return {"status": "success", "data": {"permissions": permissions}}
    except AppFileNotFoundError as e:
        # It's not an error if the permissions file doesn't exist; it just means no permissions are set.
        return {
            "status": "success",
            "data": {"permissions": []},
            "message": f"{e}",
        }
    except BSMError as e:
        logger.error(
            f"API: Failed to get permissions for '{server_name}': {e}", exc_info=True
        )
        return {"status": "error", "message": f"Failed to get permissions: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error getting permissions for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Unexpected error: {e}"}


# --- Server Properties ---
@plugin_method("get_server_properties_api")
def get_server_properties_api(server_name: str) -> Dict[str, Any]:
    """Reads and returns the `server.properties` file for a server.

    Delegates to
    :meth:`~.core.bedrock_server.BedrockServer.get_server_properties`
    to parse the file into a dictionary.

    Args:
        server_name (str): The name of the server.

    Returns:
        Dict[str, Any]: A dictionary with the operation result.
        On success: ``{"status": "success", "properties": Dict[str, str]}``
        On error (e.g., file not found): ``{"status": "error", "message": "<error_message>"}``

    Raises:
        MissingArgumentError: If `server_name` is empty (though caught before core call).
        AppFileNotFoundError: If ``server.properties`` does not exist.
        ConfigParseError: If reading ``server.properties`` fails due to OS or parsing issues.
    """
    if not server_name:
        return {"status": "error", "message": "Server name cannot be empty."}
    try:
        server = BedrockServer(server_name)
        properties = server.get_server_properties()
        return {"status": "success", "properties": properties}
    except AppFileNotFoundError as e:
        return {"status": "error", "message": str(e)}
    except BSMError as e:
        logger.error(
            f"API: Failed to get properties for '{server_name}': {e}", exc_info=True
        )
        return {"status": "error", "message": f"Failed to get properties: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error getting properties for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Unexpected error: {e}"}


@plugin_method("validate_server_property_value")
def validate_server_property_value(property_name: str, value: str) -> Dict[str, str]:
    """Validates a single server property value based on known rules.

    This is a stateless helper function used before modifying properties. It checks
    specific rules for properties like ``server-name`` (MOTD length, no semicolons),
    ``level-name`` (character set, length), network ports (numeric range),
    and certain numeric game settings (``max-players``, ``view-distance``,
    ``tick-distance``).

    Properties not explicitly checked by this function are considered valid by default
    by this validator (though the server itself might have further constraints).

    Args:
        property_name (str): The name of the server property (e.g., 'level-name',
            'server-port').
        value (str): The string value of the property to validate.

    Returns:
        Dict[str, str]: A dictionary with validation result.
        If valid: ``{"status": "success"}``
        If invalid: ``{"status": "error", "message": "<validation_error_detail>"}``
    """
    logger.debug(
        f"API: Validating server property: '{property_name}', Value: '{value}'"
    )
    if value is None:
        value = ""
    # Validate server-name (MOTD)
    if property_name == "server-name":
        if ";" in value:
            return {
                "status": "error",
                "message": "server-name cannot contain semicolons.",
            }
        if len(value) > 100:
            return {
                "status": "error",
                "message": "server-name is too long (max 100 chars).",
            }
    # Validate level-name (world folder name)
    elif property_name == "level-name":
        if not re.fullmatch(r"[a-zA-Z0-9_\-]+", value.replace(" ", "_")):
            return {
                "status": "error",
                "message": "level-name: use letters, numbers, underscore, hyphen.",
            }
        if len(value) > 80:
            return {
                "status": "error",
                "message": "level-name is too long (max 80 chars).",
            }
    # Validate network ports
    elif property_name in ("server-port", "server-portv6"):
        try:
            port = int(value)
            if not (1024 <= port <= 65535):
                raise ValueError()
        except (ValueError, TypeError):
            return {
                "status": "error",
                "message": f"{property_name}: must be a number 1024-65535.",
            }
    # Validate numeric game settings
    elif property_name in ("max-players", "view-distance", "tick-distance"):
        try:
            num_val = int(value)
            if property_name == "max-players" and num_val < 1:
                raise ValueError("Must be >= 1")
            if property_name == "view-distance" and num_val < 5:
                raise ValueError("Must be >= 5")
            if property_name == "tick-distance" and not (4 <= num_val <= 12):
                raise ValueError("Must be between 4-12")
        except (ValueError, TypeError):
            range_msg = "a positive number"
            if property_name == "view-distance":
                range_msg = "a number >= 5"
            if property_name == "tick-distance":
                range_msg = "a number between 4 and 12"
            msg = f"Invalid value for '{property_name}'. Must be {range_msg}."
            return {"status": "error", "message": msg}
    # Property is valid or has no specific validation rule.
    return {"status": "success"}


@plugin_method("modify_server_properties")
def modify_server_properties(
    server_name: str,
    properties_to_update: Dict[str, str],
    restart_after_modify: bool = True,
) -> Dict[str, str]:
    """Modifies one or more properties in `server.properties`.

    This function first validates all provided properties using
    :func:`~.validate_server_property_value`. If all validations pass, it
    then uses the :func:`~bedrock_server_manager.api.utils.server_lifecycle_manager`
    to manage the server's state (stopping it if `restart_after_modify` is ``True``).
    Within the managed context, it applies each change by calling
    :meth:`~.core.bedrock_server.BedrockServer.set_server_property`.
    If `restart_after_modify` is ``True``, the server is restarted only if all
    properties are successfully set and the lifecycle manager completes without error.
    Triggers ``before_properties_change`` and ``after_properties_change`` plugin events.

    Args:
        server_name (str): The name of the server to modify.
        properties_to_update (Dict[str, str]): A dictionary of property keys
            and their new string values.
        restart_after_modify (bool, optional): If ``True``, the server will be
            stopped before applying changes and restarted afterwards if successful.
            Defaults to ``True``.

    Returns:
        Dict[str, str]: A dictionary with the operation result.
        On success: ``{"status": "success", "message": "Server properties updated successfully."}``
        On error (validation, file op, etc.): ``{"status": "error", "message": "<error_message>"}``

    Raises:
        InvalidServerNameError: If `server_name` is empty.
        TypeError: If `properties_to_update` is not a dictionary.
        UserInputError: If any property value fails validation via
            :func:`~.validate_server_property_value` or contains invalid characters.
        AppFileNotFoundError: If ``server.properties`` does not exist.
        FileOperationError: If reading/writing ``server.properties`` fails.
        ServerStopError/ServerStartError: If server stop/start fails during lifecycle management.
    """
    if not server_name:
        raise InvalidServerNameError("Server name required.")
    if not isinstance(properties_to_update, dict):
        raise TypeError("Properties must be a dict.")

    plugin_manager.trigger_event(
        "before_properties_change",
        server_name=server_name,
        properties=properties_to_update,
    )

    result = {}
    try:
        # First, validate all properties before making any changes.
        for name, val_str in properties_to_update.items():
            val_res = validate_server_property_value(
                name, str(val_str) if val_str is not None else ""
            )
            if val_res.get("status") == "error":
                raise UserInputError(
                    f"Validation failed for '{name}': {val_res.get('message')}"
                )

        # Use a context manager to handle stopping and restarting the server.
        with server_lifecycle_manager(
            server_name, stop_before=restart_after_modify, restart_on_success_only=True
        ):
            server = BedrockServer(server_name)
            for prop_name, prop_value in properties_to_update.items():
                server.set_server_property(prop_name, prop_value)

        result = {
            "status": "success",
            "message": "Server properties updated successfully.",
        }

    except (BSMError, FileNotFoundError, UserInputError) as e:
        logger.error(
            f"API: Failed to modify properties for '{server_name}': {e}", exc_info=True
        )
        result = {"status": "error", "message": f"Failed to modify properties: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error modifying properties for '{server_name}': {e}",
            exc_info=True,
        )
        result = {"status": "error", "message": f"Unexpected error: {e}"}
    finally:
        plugin_manager.trigger_event(
            "after_properties_change", server_name=server_name, result=result
        )

    return result


# --- INSTALL/UPDATE FUNCTIONS ---
@plugin_method("install_new_server")
def install_new_server(
    server_name: str, target_version: str = "LATEST"
) -> Dict[str, Any]:
    """Installs a new Bedrock server.

    This involves validating the server name, ensuring the target directory
    doesn't already exist, then creating the server directory, downloading
    the specified version of the server software (via
    :meth:`~.core.bedrock_server.BedrockServer.install_or_update`),
    extracting files, setting permissions, and setting up initial configuration.
    Triggers ``before_server_install`` and ``after_server_install`` plugin events.

    Args:
        server_name (str): The name for the new server. Must be unique and
            follow valid naming conventions (checked by
            :func:`~bedrock_server_manager.api.utils.validate_server_name_format`).
        target_version (str, optional): The server version to install
            (e.g., '1.20.10.01', 'LATEST', 'PREVIEW'). Defaults to 'LATEST'.

    Returns:
        Dict[str, Any]: A dictionary with the operation result.
        On success: ``{"status": "success", "version": "<installed_version>", "message": "Server '<name>' installed..."}``
        On error: ``{"status": "error", "message": "<error_message>"}``

    Raises:
        MissingArgumentError: If `server_name` is empty.
        UserInputError: If `server_name` format is invalid or directory already exists.
        FileOperationError: If base server directory (``paths.servers``) isn't configured,
            or for other file I/O issues during installation.
        DownloadError: If server software download fails.
        ExtractError: If downloaded archive cannot be extracted.
        PermissionsError: If filesystem permissions cannot be set.
        BSMError: For other application-specific errors.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")

    plugin_manager.trigger_event(
        "before_server_install", server_name=server_name, target_version=target_version
    )

    result = {}
    try:
        # Perform pre-flight checks before creating anything.
        val_res = validate_server_name_format(server_name)
        if val_res.get("status") == "error":
            raise UserInputError(val_res.get("message"))

        base_dir = settings.get("paths.servers")
        if not base_dir:
            raise FileOperationError("BASE_DIR not configured in settings.")
        if os.path.exists(os.path.join(base_dir, server_name)):
            raise UserInputError(
                f"Directory for server '{server_name}' already exists."
            )

        logger.info(
            f"API: Installing new server '{server_name}', target version '{target_version}'."
        )
        server = BedrockServer(server_name)
        server.install_or_update(target_version)
        result = {
            "status": "success",
            "version": server.get_version(),
            "message": f"Server '{server_name}' installed successfully to version {server.get_version()}.",
        }

    except BSMError as e:
        logger.error(
            f"API: Installation failed for '{server_name}': {e}", exc_info=True
        )
        result = {"status": "error", "message": f"Server installation failed: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error installing '{server_name}': {e}", exc_info=True
        )
        result = {"status": "error", "message": f"An unexpected error occurred: {e}"}
    finally:
        plugin_manager.trigger_event(
            "after_server_install", server_name=server_name, result=result
        )

    return result


@plugin_method("update_server")
def update_server(server_name: str, send_message: bool = True) -> Dict[str, Any]:
    """Updates an existing server to its configured target version.

    The process is as follows:

    1. Retrieves the server's target version using
       :meth:`~.core.bedrock_server.BedrockServer.get_target_version`.
    2. Checks if an update is necessary via
       :meth:`~.core.bedrock_server.BedrockServer.is_update_needed`.
    3. If an update is needed:

        - Uses :func:`~bedrock_server_manager.api.utils.server_lifecycle_manager`
          to stop the server (if running and `send_message` is True, a notification
          may be sent before stopping).
        - Backs up all server data using
          :meth:`~.core.bedrock_server.BedrockServer.backup_all_data`.
        - Performs the update using
          :meth:`~.core.bedrock_server.BedrockServer.install_or_update`.
        - The lifecycle manager attempts to restart the server.

    Triggers ``before_server_update`` and ``after_server_update`` plugin events.

    Args:
        server_name (str): The name of the server to update.
        send_message (bool, optional): If ``True`` and the server is running,
            attempts to send a notification message to the server console before
            it's stopped for the update. Defaults to ``True``.

    Returns:
        Dict[str, Any]: A dictionary with the operation result.

        If no update needed: ``{"status": "success", "updated": False, "message": "Server is already up-to-date."}``
        On successful update: ``{"status": "success", "updated": True, "new_version": "<version>", "message": "Server '<name>' updated..."}``
        On error: ``{"status": "error", "message": "<error_message>"}``

    Raises:
        InvalidServerNameError: If `server_name` is empty.
        ServerStopError: If stopping the server fails.
        BackupRestoreError: If the pre-update backup fails.
        DownloadError: If server software download fails during update.
        ExtractError: If downloaded archive cannot be extracted.
        PermissionsError: If filesystem permissions cannot be set.
        FileOperationError: For other file I/O issues.
        BSMError: For other application-specific errors.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    result = {}
    try:
        server = BedrockServer(server_name)
        target_version = server.get_target_version()

        plugin_manager.trigger_event(
            "before_server_update",
            server_name=server_name,
            target_version=target_version,
        )

        logger.info(
            f"API: Updating server '{server_name}'. Send message: {send_message}"
        )
        # Check if an update is actually necessary.
        if not server.is_update_needed(target_version):
            return {
                "status": "success",
                "updated": False,
                "message": "Server is already up-to-date.",
            }

        # Use the lifecycle manager to handle the stop/start cycle.
        with server_lifecycle_manager(
            server_name,
            stop_before=True,
            start_after=True,
            restart_on_success_only=True,
        ):
            logger.info(f"API: Backing up '{server_name}' before update...")
            server.backup_all_data()
            logger.info(
                f"API: Performing update for '{server_name}' to target '{target_version}'..."
            )
            server.install_or_update(target_version)

        result = {
            "status": "success",
            "updated": True,
            "new_version": server.get_version(),
            "message": f"Server '{server_name}' updated successfully to {server.get_version()}.",
        }

    except BSMError as e:
        logger.error(f"API: Update failed for '{server_name}': {e}", exc_info=True)
        result = {"status": "error", "message": f"Server update failed: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error updating '{server_name}': {e}", exc_info=True
        )
        result = {"status": "error", "message": f"An unexpected error occurred: {e}"}
    finally:
        plugin_manager.trigger_event(
            "after_server_update", server_name=server_name, result=result
        )

    return result
