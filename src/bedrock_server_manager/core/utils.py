# bedrock_server_manager/core/utils.py
"""
Provides low-level core utility functions for server management.

This module contains a collection of helper functions that perform specific,
atomic tasks related to server management. These utilities are designed to be
used by higher-level components like the :class:`~.core.bedrock_server.BedrockServer`
or API endpoints.

Key functions include:

    - :func:`core_validate_server_name_format`: Validates server names against a regex.

"""

import logging
import os
import re
from typing import Any, Dict, List, Tuple

from ..context import AppContext
from ..error import (
    AppFileNotFoundError,
    ConfigurationError,
    FileOperationError,
    InvalidServerNameError,
    MissingArgumentError,
)

logger = logging.getLogger(__name__)

# --- Server Stuff ---


def core_validate_server_name_format(server_name: str) -> None:
    """
    Validates the format of a server name against a specific pattern.

    The function checks that the server name is not empty and contains only
    alphanumeric characters (a-z, A-Z, 0-9), hyphens (-), and underscores (_).
    This helps prevent issues with file paths and system commands.

    Args:
        server_name (str): The server name string to validate.

    Raises:
        :class:`~.error.InvalidServerNameError`: If the server name is empty or
            contains invalid characters.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    if not re.fullmatch(r"^[a-zA-Z0-9_-]+$", server_name):
        raise InvalidServerNameError(
            "Invalid server name format. Only use letters (a-z, A-Z), "
            "numbers (0-9), hyphens (-), and underscores (_)."
        )
    logger.debug(f"Server name '{server_name}' format is valid.")


# --- Server Discovery and Validation ---


def validate_server(server_name: str, app_context: AppContext) -> bool:
    """Validates if a given server name corresponds to a valid installation."""
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty for validation.")

    logger.debug(f"BSM: Validating server '{server_name}' using BedrockServer class.")
    try:
        server_instance = app_context.get_server(server_name)
        is_valid = server_instance.is_installed()
        if is_valid:
            logger.debug(f"BSM: Server '{server_name}' validation successful.")
        else:
            logger.debug(
                f"BSM: Server '{server_name}' validation failed (directory or executable missing)."
            )
        return is_valid
    except (
        ValueError,
        MissingArgumentError,
        ConfigurationError,
        InvalidServerNameError,
        Exception,
    ) as e_val:
        logger.warning(
            f"BSM: Validation failed for server '{server_name}' due to an error: {e_val}"
        )
        return False


def get_servers_data(app_context: AppContext) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Discovers and retrieves status data for all valid server instances."""
    servers_data: List[Dict[str, Any]] = []
    error_messages: List[str] = []

    base_dir = app_context.settings.get("paths.servers")
    if not base_dir or not os.path.isdir(base_dir):
        raise AppFileNotFoundError(str(base_dir), "Server base directory")

    for server_name_candidate in os.listdir(base_dir):
        potential_server_path = os.path.join(base_dir, server_name_candidate)
        if not os.path.isdir(potential_server_path):
            continue

        try:
            server = app_context.get_server(server_name_candidate)

            if not server.is_installed():
                logger.debug(
                    f"Skipping '{server_name_candidate}': Not a valid server installation."
                )
                continue

            status = server.get_status()
            version = server.get_version()
            servers_data.append(
                {
                    "name": server.server_name,
                    "status": status,
                    "version": version,
                    "player_count": server.player_count,
                    "players": getattr(server, "players", []),
                }
            )

        except (FileOperationError, ConfigurationError, InvalidServerNameError) as e:
            msg = f"Could not get info for server '{server_name_candidate}': {e}"
            logger.warning(msg)
            error_messages.append(msg)
        except Exception as e:
            msg = f"An unexpected error occurred while processing server '{server_name_candidate}': {e}"
            logger.error(msg, exc_info=True)
            error_messages.append(msg)

    servers_data.sort(key=lambda s: s.get("name", "").lower())
    return servers_data, error_messages
