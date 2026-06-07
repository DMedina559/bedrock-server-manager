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
from typing import Any, Dict

from ..context import AppContext
from ..error import (
    BSMError,
    InvalidServerNameError,
)
from ..plugins import plugin_method

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
