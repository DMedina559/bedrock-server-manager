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
import platform
from typing import Dict, Any

# Plugin system imports to bridge API functionality.
from bedrock_server_manager import plugin_manager
from bedrock_server_manager.cli.plugins import plugin
from bedrock_server_manager.plugins.api_bridge import plugin_method

# Local application imports.
from bedrock_server_manager.core.bedrock_server import BedrockServer
from bedrock_server_manager.error import (
    BSMError,
    InvalidServerNameError,
    MissingArgumentError,
    UserInputError,
)

logger = logging.getLogger(__name__)


@plugin_method("get_bedrock_process_info")
def get_bedrock_process_info(server_name: str) -> Dict[str, Any]:
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
        server = BedrockServer(server_name)
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


def create_server_service(server_name: str, autostart: bool = False) -> Dict[str, str]:
    """Creates (or updates) a system service for the server.

    On Linux, this creates a systemd user service. On Windows, this creates a
    Windows Service (typically requires Administrator privileges).

    This function calls :meth:`~.core.bedrock_server.BedrockServer.create_service`
    to generate and install the service definition. Based on the `autostart` flag,
    it then calls either :meth:`~.core.bedrock_server.BedrockServer.enable_service`
    or :meth:`~.core.bedrock_server.BedrockServer.disable_service`.
    Triggers ``before_service_change`` and ``after_service_change`` plugin events.

    Args:
        server_name (str): The name of the server for which to create the service.
        autostart (bool, optional): If ``True``, the service will be enabled to
            start automatically on system boot/login. If ``False``, it will be
            created but left disabled (or set to manual start). Defaults to ``False``.

    Returns:
        Dict[str, str]: A dictionary with the operation result.
        On success: ``{"status": "success", "message": "System service created and <enabled/disabled> successfully."}``
        On error: ``{"status": "error", "message": "<error_message>"}``

    Raises:
        InvalidServerNameError: If `server_name` is not provided.
        BSMError: Can be raised by the underlying service management methods for
            various reasons, including:
            - :class:`~.error.SystemError` if the OS is unsupported or system commands fail.
            - :class:`~.error.PermissionsError` if lacking necessary privileges (especially on Windows).
            - :class:`~.error.CommandNotFoundError` if essential system utilities are missing.
            - :class:`~.error.FileOperationError` if service file creation/modification fails.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    plugin_manager.trigger_event(
        "before_service_change", server_name=server_name, action="create"
    )

    result = {}
    try:
        server = BedrockServer(server_name)
        # These methods are implemented on BedrockServer, which delegates to
        # the appropriate OS-specific mixin.
        server.create_service()

        # Enable or disable the service for autostart based on the flag.
        if autostart:
            server.enable_service()
            action = "created and enabled"
        else:
            server.disable_service()
            action = "created and disabled"

        result = {
            "status": "success",
            "message": f"System service {action} successfully.",
        }

    except BSMError as e:
        # This will catch SystemError, PermissionsError, etc. from the mixins.
        logger.error(
            f"API: Failed to configure system service for '{server_name}': {e}",
            exc_info=True,
        )
        result = {
            "status": "error",
            "message": f"Failed to configure system service: {e}",
        }
    except Exception as e:
        logger.error(
            f"API: Unexpected error creating system service for '{server_name}': {e}",
            exc_info=True,
        )
        result = {
            "status": "error",
            "message": f"Unexpected error creating system service: {e}",
        }
    finally:
        plugin_manager.trigger_event(
            "after_service_change",
            server_name=server_name,
            action="create",
            result=result,
        )

    return result


def set_autoupdate(server_name: str, autoupdate_value: str) -> Dict[str, str]:
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

    plugin_manager.trigger_event(
        "before_autoupdate_change", server_name=server_name, new_value=value_bool
    )

    result = {}
    try:
        logger.info(
            f"API: Setting 'autoupdate' config for server '{server_name}' to {value_bool}..."
        )
        server = BedrockServer(server_name)
        server.set_autoupdate(value_bool)
        result = {
            "status": "success",
            "message": f"Autoupdate setting for '{server_name}' updated to {value_bool}.",
        }

    except BSMError as e:
        logger.error(
            f"API: Failed to set autoupdate config for '{server_name}': {e}",
            exc_info=True,
        )
        result = {"status": "error", "message": f"Failed to set autoupdate config: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error setting autoupdate for '{server_name}': {e}",
            exc_info=True,
        )
        result = {
            "status": "error",
            "message": f"Unexpected error setting autoupdate: {e}",
        }
    finally:
        plugin_manager.trigger_event(
            "after_autoupdate_change", server_name=server_name, result=result
        )

    return result


def enable_server_service(server_name: str) -> Dict[str, str]:
    """Enables the system service for autostart.

    On Linux, this enables the systemd user service. On Windows, this sets the
    Windows Service start type to 'Automatic' (typically requires Administrator
    privileges). This is achieved by calling
    :meth:`~.core.bedrock_server.BedrockServer.enable_service`.
    Triggers ``before_service_change`` and ``after_service_change`` plugin events.

    Args:
        server_name (str): The name of the server whose service is to be enabled.

    Returns:
        Dict[str, str]: A dictionary with the operation result.
        On success: ``{"status": "success", "message": "Service for '<name>' enabled successfully."}``
        On error: ``{"status": "error", "message": "<error_message>"}``

    Raises:
        InvalidServerNameError: If `server_name` is not provided.
        BSMError: Can be raised by the underlying service management methods,
            e.g., :class:`~.error.SystemError` if the service does not exist or
            OS commands fail, or :class:`~.error.PermissionsError` on Windows
            if not run with sufficient privileges.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    plugin_manager.trigger_event(
        "before_service_change", server_name=server_name, action="enable"
    )

    result = {}
    try:
        server = BedrockServer(server_name)
        server.enable_service()
        result = {
            "status": "success",
            "message": f"Service for '{server_name}' enabled successfully.",
        }

    except BSMError as e:
        logger.error(
            f"API: Failed to enable system service for '{server_name}': {e}",
            exc_info=True,
        )
        result = {"status": "error", "message": f"Failed to enable service: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error enabling service for '{server_name}': {e}",
            exc_info=True,
        )
        result = {
            "status": "error",
            "message": f"Unexpected error enabling service: {e}",
        }
    finally:
        plugin_manager.trigger_event(
            "after_service_change",
            server_name=server_name,
            action="enable",
            result=result,
        )

    return result


def disable_server_service(server_name: str) -> Dict[str, str]:
    """Disables the system service from autostarting.

    On Linux, this disables the systemd user service. On Windows, this sets
    the Windows Service start type to 'Disabled' (typically requires
    Administrator privileges). This is achieved by calling
    :meth:`~.core.bedrock_server.BedrockServer.disable_service`.
    Triggers ``before_service_change`` and ``after_service_change`` plugin events.

    Args:
        server_name (str): The name of the server whose service is to be disabled.

    Returns:
        Dict[str, str]: A dictionary with the operation result.
        On success: ``{"status": "success", "message": "Service for '<name>' disabled successfully."}``
        On error: ``{"status": "error", "message": "<error_message>"}``

    Raises:
        InvalidServerNameError: If `server_name` is not provided.
        BSMError: Can be raised by the underlying service management methods,
            e.g., :class:`~.error.SystemError` if the service does not exist or
            OS commands fail, or :class:`~.error.PermissionsError` on Windows
            if not run with sufficient privileges.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    plugin_manager.trigger_event(
        "before_service_change", server_name=server_name, action="disable"
    )

    result = {}
    try:
        server = BedrockServer(server_name)
        server.disable_service()
        result = {
            "status": "success",
            "message": f"Service for '{server_name}' disabled successfully.",
        }

    except BSMError as e:
        logger.error(
            f"API: Failed to disable system service for '{server_name}': {e}",
            exc_info=True,
        )
        result = {"status": "error", "message": f"Failed to disable service: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error disabling service for '{server_name}': {e}",
            exc_info=True,
        )
        result = {
            "status": "error",
            "message": f"Unexpected error disabling service: {e}",
        }
    finally:
        plugin_manager.trigger_event(
            "after_service_change",
            server_name=server_name,
            action="disable",
            result=result,
        )

    return result
