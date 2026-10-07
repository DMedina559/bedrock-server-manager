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

from ..context import AppContext
from ..error import (
    BSMError,
    InvalidServerNameError,
)
from ..plugins.api_bridge import api_method
from .models.system import (
    GetBedrockProcessInfoRequest,
    GetBedrockProcessInfoResponse,
    GetServerRunningStatusRequest,
    GetServerRunningStatusResponse,
)

logger = logging.getLogger(__name__)


@api_method("get_server_running_status")
async def get_server_running_status(
    request: GetServerRunningStatusRequest, *, app_context: AppContext
) -> GetServerRunningStatusResponse:
    """Checks if the server process is currently running.

    Accepts GetServerRunningStatusRequest and returns GetServerRunningStatusResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    server_name = request.server_name
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    logger.info(f"API: Checking running status for server '{server_name}'...")
    try:
        server = app_context.get_server(server_name)
        is_running = await server.is_running()
        logger.debug(
            f"API: is_running() check for '{server_name}' returned: {is_running}"
        )
        return GetServerRunningStatusResponse.model_validate(
            {"status": "success", "is_running": is_running}
        )
    except BSMError as e:
        logger.error(
            f"API: Error checking running status for '{server_name}': {e}",
            exc_info=True,
        )
        raise
    except Exception as e:
        logger.error(
            f"API: Unexpected error checking running status for '{server_name}': {e}",
            exc_info=True,
        )
        raise


@api_method("get_bedrock_process_info")
async def get_bedrock_process_info(
    request: GetBedrockProcessInfoRequest, *, app_context: AppContext
) -> GetBedrockProcessInfoResponse:
    """Retrieves resource usage for a running Bedrock server process.

    Accepts GetBedrockProcessInfoRequest and returns GetBedrockProcessInfoResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    server_name = request.server_name
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    logger.debug(f"API: Getting process info for server '{server_name}'...")
    try:
        server = app_context.get_server(server_name)
        process_info = await server.get_process_info()
        if process_info is None:
            return GetBedrockProcessInfoResponse.model_validate(
                {
                    "status": "success",
                    "message": f"Server process '{server_name}' not found or is inaccessible.",
                    "process_info": None,
                }
            )
        else:
            return GetBedrockProcessInfoResponse.model_validate(
                {"status": "success", "process_info": process_info}
            )
    except BSMError as e:
        logger.error(
            f"API: Failed to get process info for '{server_name}': {e}", exc_info=True
        )
        raise
    except Exception as e:
        logger.error(
            f"API: Unexpected error getting process info for '{server_name}': {e}",
            exc_info=True,
        )
        raise
