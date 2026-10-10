# bedrock_server_manager/utils/server.py
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
from ..logging import log_operation_error

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
    logger.debug("Server name '%s' format is valid.", server_name)


# --- Server Discovery and Validation ---


async def validate_server(server_name: str, app_context: AppContext) -> bool:
    """Validates if a given server name corresponds to a valid installation."""
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty for validation.")

    logger.debug("Validating server '%s' using BedrockServer class.", server_name)
    try:
        server_instance = app_context.get_server(server_name)
        is_valid = await server_instance.is_installed()
        if is_valid:
            logger.debug("Server '%s' validation successful.", server_name)
        else:
            logger.debug(
                "Server '%s' validation failed (directory or executable missing).",
                server_name,
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
            "Validation failed for server '%s' due to an error: %s", server_name, e_val
        )
        return False


async def get_servers_data(
    app_context: AppContext,
) -> Tuple[List[Dict[str, Any]], List[str]]:
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

            if not await server.is_installed():
                logger.debug(
                    "Skipping '%s': Not a valid server installation.",
                    server_name_candidate,
                )
                continue

            servers_data.append(
                (await server.get_summary_info()).model_dump(mode="json")
            )

        except (FileOperationError, ConfigurationError, InvalidServerNameError) as e:
            msg = f"Could not get info for server '{server_name_candidate}': {e}"
            logger.warning(msg)
            error_messages.append(msg)
        except Exception as e:
            msg = f"An unexpected error occurred while processing server '{server_name_candidate}': {e}"
            log_operation_error(logger, msg, error=e)
            error_messages.append(msg)

    servers_data.sort(key=lambda s: s.get("name", "").lower())
    return servers_data, error_messages
