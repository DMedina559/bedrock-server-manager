# bedrock_server_manager/api/info.py
"""Provides API functions for retrieving server-specific information.

This module offers read-only functions to query details about individual
Bedrock server instances. It wraps methods of the
:class:`~bedrock_server_manager.core.bedrock_server.BedrockServer` class
to expose information such as:

- Current runtime status (:func:`~.get_server_running_status`).
- Last known status from configuration (:func:`~.get_server_config_status`).
- Installed server version (:func:`~.get_server_installed_version`).

Each function returns a dictionary suitable for JSON serialization, indicating
the outcome of the request and the retrieved data. These are exposed to the
plugin system via
:func:`~bedrock_server_manager.plugins.api_bridge.plugin_method`.
"""

import logging
from typing import Dict, Any

# Plugin system imports to bridge API functionality.
from bedrock_server_manager.plugins.api_bridge import plugin_method

# Local application imports.
from bedrock_server_manager.core.bedrock_server import BedrockServer
from bedrock_server_manager.error import (
    BSMError,
    InvalidServerNameError,
)

logger = logging.getLogger(__name__)


@plugin_method("get_server_running_status")
def get_server_running_status(server_name: str) -> Dict[str, Any]:
    """Checks if the server process is currently running.

    This function queries the operating system to determine if the Bedrock
    server process associated with the given server name is active by calling
    :meth:`~.core.bedrock_server.BedrockServer.is_running`.

    Args:
        server_name (str): The name of the server to check.

    Returns:
        Dict[str, Any]: A dictionary with the operation result.
        On success: ``{"status": "success", "is_running": bool}``
        (``is_running`` is ``True`` if the process is active, ``False`` otherwise).
        On error: ``{"status": "error", "message": "<error_message>"}``.

    Raises:
        InvalidServerNameError: If `server_name` is not provided.
        BSMError: Can be raised by
            :class:`~.core.bedrock_server.BedrockServer` instantiation or
            if `is_running` encounters a critical issue (e.g., misconfiguration).
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.info(f"API: Checking running status for server '{server_name}'...")
    try:
        server = BedrockServer(server_name)
        is_running = server.is_running()
        logger.debug(
            f"API: is_running() check for '{server_name}' returned: {is_running}"
        )
        return {"status": "success", "is_running": is_running}
    except BSMError as e:
        logger.error(
            f"API: Error checking running status for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Error checking running status: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error checking running status for '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Unexpected error checking running status: {e}",
        }


@plugin_method("get_server_config_status")
def get_server_config_status(server_name: str) -> Dict[str, Any]:
    """Gets the status from the server's configuration file.

    This function reads the 'status' field (e.g., 'RUNNING', 'STOPPED')
    from the server's JSON configuration file via
    :meth:`~.core.bedrock_server.BedrockServer.get_status_from_config`.
    Note that this reflects the last known state written to the configuration
    and may not match the actual live process status if the server crashed or
    was managed externally.

    Args:
        server_name (str): The name of the server.

    Returns:
        Dict[str, Any]: A dictionary with the operation result.
        On success: ``{"status": "success", "config_status": "<status_string>"}``
        (e.g., "RUNNING", "STOPPED", "UNKNOWN").
        On error: ``{"status": "error", "message": "<error_message>"}``.

    Raises:
        InvalidServerNameError: If `server_name` is not provided.
        BSMError: Can be raised by
            :class:`~.core.bedrock_server.BedrockServer` instantiation or by
            the underlying configuration access methods (e.g., for file I/O
            or parsing errors).
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.info(f"API: Getting config status for server '{server_name}'...")
    try:
        server = BedrockServer(server_name)
        status = server.get_status_from_config()
        logger.debug(
            f"API: get_status_from_config() for '{server_name}' returned: '{status}'"
        )
        return {"status": "success", "config_status": status}
    except BSMError as e:
        logger.error(
            f"API: Error retrieving config status for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Error retrieving config status: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error getting config status for '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Unexpected error getting config status: {e}",
        }


@plugin_method("get_server_installed_version")
def get_server_installed_version(server_name: str) -> Dict[str, Any]:
    """Gets the installed version from the server's configuration file.

    This function reads the 'installed_version' field from the server's
    JSON configuration file via
    :meth:`~.core.bedrock_server.BedrockServer.get_version`.
    If the version is not found or an error occurs during retrieval,
    it typically returns 'UNKNOWN'.

    Args:
        server_name (str): The name of the server.

    Returns:
        Dict[str, Any]: A dictionary with the operation result.
        On success: ``{"status": "success", "installed_version": "<version_string>"}``
        (e.g., "1.20.10.01", "UNKNOWN").
        On error: ``{"status": "error", "message": "<error_message>"}``.

    Raises:
        InvalidServerNameError: If `server_name` is not provided.
        BSMError: Can be raised by
            :class:`~.core.bedrock_server.BedrockServer` instantiation or by
            the underlying configuration access methods.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.info(f"API: Getting installed version for server '{server_name}'...")
    try:
        server = BedrockServer(server_name)
        version = server.get_version()
        logger.debug(f"API: get_version() for '{server_name}' returned: '{version}'")
        return {"status": "success", "installed_version": version}
    except BSMError as e:
        logger.error(
            f"API: Error retrieving installed version for '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Error retrieving installed version: {e}",
        }
    except Exception as e:
        logger.error(
            f"API: Unexpected error getting installed version for '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Unexpected error getting installed version: {e}",
        }
