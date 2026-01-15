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
import re

# Local imports
from ..error import InvalidServerNameError

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
