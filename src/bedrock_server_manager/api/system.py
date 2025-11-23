# bedrock_server_manager/api/system.py
"""Provides API functions for system-level server interactions and information.

This module serves as an interface for querying system-related information about
server processes and for managing their integration with the host operating system's
service management capabilities. It primarily orchestrates calls to the
:class:`~bedrock_server_manager.core.bedrock_server.BedrockServer` class.

Key functionalities include:
    - Querying server process resource usage (e.g., PID, CPU, memory) via
      :func:`~.get_bedrock_process_info`.
    - Managing OS-level services (systemd on Linux, Windows Services on Windows)
      for servers, including creation (:func:`~.create_server_service`),
      enabling (:func:`~.enable_server_service`), and disabling
      (:func:`~.disable_server_service`) auto-start.
    - Configuring server-specific settings like autoupdate behavior via
      :func:`~.set_autoupdate`.

These functions are designed for use by higher-level application components,
such as the web UI or CLI, to provide system-level control and monitoring.
"""
import logging
from typing import Dict, Any, Optional

# Plugin system imports to bridge API functionality.
from ..plugins import plugin_method

# Local application imports.
from ..error import (
    BSMError,
    InvalidServerNameError,
    MissingArgumentError,
    UserInputError,
)
from ..context import AppContext

logger = logging.getLogger(__name__)


@plugin_method("get_bedrock_process_info")
def get_bedrock_process_info(
    server_name: str, app_context: AppContext
) -> Dict[str, Any]:
    """Retrieves resource usage for a running Bedrock server process.

    This function queries the system for the server's process by calling
    :meth:`~.core.bedrock_server.BedrockServer.get_process_info`
    and returns details like PID, CPU usage, memory consumption, and uptime.

    Args:
        server_name (str): The name of the server to query.

    Returns:
        Dict[str, Any]: A dictionary with the operation status and process information.
        On success with a running process:
        ``{"status": "success", "process_info": {"pid": int, "cpu_percent": float, "memory_mb": float, "uptime": str}}``.
        If the process is not found or inaccessible:
        ``{"status": "success", "process_info": None, "message": "Server process '<name>' not found..."}``.
        On error during retrieval: ``{"status": "error", "message": "<error_message>"}``.

    Raises:
        InvalidServerNameError: If `server_name` is not provided.
        BSMError: Can be raised by
            :class:`~.core.bedrock_server.BedrockServer` instantiation if core
            application settings are misconfigured, or by ``get_process_info``
            if ``psutil`` is unavailable or encounters issues.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.debug(f"API: Getting process info for server '{server_name}'...")
    try:
        server = app_context.get_server(server_name)
        process_info = server.get_process_info()

        # If get_process_info returns None, the server is not running or inaccessible.
        if process_info is None:
            return {
                "status": "success",
                "message": f"Server process '{server_name}' not found or is inaccessible.",
                "process_info": None,
            }
        else:
            return {"status": "success", "process_info": process_info}
    except BSMError as e:
        logger.error(
            f"API: Failed to get process info for '{server_name}': {e}", exc_info=True
        )
        return {"status": "error", "message": f"Error getting process info: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error getting process info for '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Unexpected error getting process info: {e}",
        }


from ..plugins.event_trigger import trigger_plugin_event


def set_autoupdate(
    server_name: str, autoupdate_value: str, app_context: AppContext
) -> Dict[str, str]:
    """Sets the 'autoupdate' flag in the server's specific JSON configuration file.

    This function modifies the server-specific JSON configuration file to
    enable or disable the automatic update check before the server starts,
    by calling :meth:`~.core.bedrock_server.BedrockServer.set_autoupdate`.
    Triggers ``before_autoupdate_change`` and ``after_autoupdate_change`` plugin events.

    Args:
        server_name (str): The name of the server.
        autoupdate_value (str): The desired state for autoupdate.
            Must be 'true' or 'false' (case-insensitive).

    Returns:
        Dict[str, str]: A dictionary with the operation result.
        On success: ``{"status": "success", "message": "Autoupdate setting for '<name>' updated to <bool_value>."}``
        On error: ``{"status": "error", "message": "<error_message>"}``

    Raises:
        InvalidServerNameError: If `server_name` is not provided.
        MissingArgumentError: If `autoupdate_value` is not provided.
        UserInputError: If `autoupdate_value` is not 'true' or 'false'.
        FileOperationError: If writing the server's JSON configuration file fails.
        ConfigParseError: If the server's JSON configuration is malformed during load/save.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    if autoupdate_value is None:
        raise MissingArgumentError("Autoupdate value cannot be empty.")

    # Validate and convert the input string to a boolean.
    value_lower = str(autoupdate_value).lower()
    if value_lower not in ("true", "false"):
        raise UserInputError("Autoupdate value must be 'true' or 'false'.")
    value_bool = value_lower == "true"

    try:
        logger.info(
            f"API: Setting 'autoupdate' config for server '{server_name}' to {value_bool}..."
        )
        server = app_context.get_server(server_name)
        server.set_autoupdate(value_bool)
        return {
            "status": "success",
            "message": f"Autoupdate setting for '{server_name}' updated to {value_bool}.",
        }

    except BSMError as e:
        logger.error(
            f"API: Failed to set autoupdate config for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Failed to set autoupdate config: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error setting autoupdate for '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Unexpected error setting autoupdate: {e}",
        }


@trigger_plugin_event(before="before_autostart_change", after="after_autostart_change")
def set_autostart(
    server_name: str, autostart_value: str, app_context: AppContext
) -> Dict[str, str]:
    """Sets the 'autostart' flag in the server's specific JSON configuration file.

    This function modifies the server-specific JSON configuration file to
    enable or disable the automatic update check before the server starts,
    by calling :meth:`~.core.bedrock_server.BedrockServer.set_autostart`.
    Triggers ``before_autostart_change`` and ``after_autostart_change`` plugin events.

    Args:
        server_name (str): The name of the server.
        autostart_value (str): The desired state for autostart.
            Must be 'true' or 'false' (case-insensitive).

    Returns:
        Dict[str, str]: A dictionary with the operation result.
        On success: ``{"status": "success", "message": "autostart setting for '<name>' updated to <bool_value>."}``
        On error: ``{"status": "error", "message": "<error_message>"}``

    Raises:
        InvalidServerNameError: If `server_name` is not provided.
        MissingArgumentError: If `autostart_value` is not provided.
        UserInputError: If `autostart_value` is not 'true' or 'false'.
        FileOperationError: If writing the server's JSON configuration file fails.
        ConfigParseError: If the server's JSON configuration is malformed during load/save.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    if autostart_value is None:
        raise MissingArgumentError("autostart value cannot be empty.")

    # Validate and convert the input string to a boolean.
    value_lower = str(autostart_value).lower()
    if value_lower not in ("true", "false"):
        raise UserInputError("autostart value must be 'true' or 'false'.")
    value_bool = value_lower == "true"

    try:
        logger.info(
            f"API: Setting 'autostart' config for server '{server_name}' to {value_bool}..."
        )
        server = app_context.get_server(server_name)
        server.set_autostart(value_bool)
        return {
            "status": "success",
            "message": f"autostart setting for '{server_name}' updated to {value_bool}.",
        }

    except BSMError as e:
        logger.error(
            f"API: Failed to set autostart config for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Failed to set autostart config: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error setting autostart for '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Unexpected error setting autostart: {e}",
        }
