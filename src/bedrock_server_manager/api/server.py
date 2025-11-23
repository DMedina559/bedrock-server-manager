# bedrock_server_manager/api/server.py
"""Provides API functions for managing Bedrock server instances.

This module serves as a key interface layer for server-specific operations within
the Bedrock Server Manager. It leverages the
:class:`~bedrock_server_manager.core.bedrock_server.BedrockServer` core class
to perform a variety of actions such as server lifecycle management (starting,
stopping, restarting), configuration (getting/setting server-specific properties),
and command execution.

The functions within this module are designed to return structured dictionary
responses, making them suitable for consumption by web API routes, command-line
interface (CLI) commands, or other parts of the application. This module also
integrates with the plugin system by exposing many of its functions as callable
APIs for plugins (via :func:`~bedrock_server_manager.plugins.api_bridge.plugin_method`)
and by triggering various plugin events during server operations.
"""
import logging
from typing import Dict, Any, Optional
import os


# Plugin system imports to bridge API functionality.
from ..plugins import plugin_method

# Local application imports.
from ..config import API_COMMAND_BLACKLIST
from ..plugins.event_trigger import trigger_plugin_event
from ..core.system import (
    get_bedrock_launcher_pid_file_path,
    remove_pid_file_if_exists,
)
from ..error import (
    BSMError,
    InvalidServerNameError,
    UserInputError,
    ServerError,
    BlockedCommandError,
    MissingArgumentError,
)
from ..context import AppContext

logger = logging.getLogger(__name__)


@plugin_method("get_server_setting")
def get_server_setting(
    server_name: str, key: str, app_context: AppContext
) -> Dict[str, Any]:
    """Reads any value from a server's specific JSON configuration file
    (e.g., ``<server_name>_config.json``) using dot-notation for keys.

    Args:
        server_name (str): The name of the server.
        key (str): The dot-notation key to read from the server's JSON
            configuration (e.g., "server_info.status", "settings.autoupdate",
            "custom.my_value").

    Returns:
        Dict[str, Any]: A dictionary containing the operation result.
        On success: ``{"status": "success", "value": <retrieved_value>}``
        On error: ``{"status": "error", "message": "<error_message>"}``
        The ``<retrieved_value>`` will be ``None`` if the key is not found.

    Raises:
        InvalidServerNameError: If `server_name` is empty.
        MissingArgumentError: If `key` is empty.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    if not key:
        raise MissingArgumentError("A 'key' must be provided.")

    logger.debug(f"API: Reading server setting for '{server_name}': Key='{key}'")
    try:
        server = app_context.get_server(server_name)
        # Use the internal method to access any key
        value = server._manage_json_config(key, "read")
        return {"status": "success", "value": value}
    except BSMError as e:
        logger.error(
            f"API: Error reading setting '{key}' for server '{server_name}': {e}"
        )
        return {"status": "error", "message": str(e)}
    except Exception as e:
        logger.error(
            f"API: Unexpected error reading setting for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": "An unexpected error occurred."}


def set_server_setting(
    server_name: str, key: str, value: Any, app_context: AppContext
) -> Dict[str, Any]:
    """Writes any value to a server's specific JSON configuration file
    (e.g., ``<server_name>_config.json``) using dot-notation for keys.
    Intermediate dictionaries will be created if they don't exist along the key path.

    Args:
        server_name (str): The name of the server.
        key (str): The dot-notation key to write to in the server's JSON
            configuration (e.g., "server_info.status", "custom.new_setting").
        value (Any): The new value to write. Must be JSON serializable.

    Returns:
        Dict[str, Any]: A dictionary containing the operation result.
        On success: ``{"status": "success", "message": "Setting '<key>' updated..."}``
        On error: ``{"status": "error", "message": "<error_message>"}``

    Raises:
        InvalidServerNameError: If `server_name` is empty.
        MissingArgumentError: If `key` is empty.
        ConfigParseError: If `value` is not JSON serializable or if an
            intermediate part of the `key` path conflicts with an existing
            non-dictionary item.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    if not key:
        raise MissingArgumentError("A 'key' must be provided.")

    logger.info(
        f"API: Writing server setting for '{server_name}': Key='{key}', Value='{value}'"
    )
    try:
        server = app_context.get_server(server_name)
        # Use the internal method to write to any key
        server._manage_json_config(key, "write", value)
        return {
            "status": "success",
            "message": f"Setting '{key}' updated for server '{server_name}'.",
        }
    except BSMError as e:
        logger.error(f"API: Error setting '{key}' for server '{server_name}': {e}")
        return {"status": "error", "message": str(e)}
    except Exception as e:
        logger.error(
            f"API: Unexpected error setting value for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": "An unexpected error occurred."}


@plugin_method("set_server_custom_value")
def set_server_custom_value(
    server_name: str, key: str, value: Any, app_context: AppContext
) -> Dict[str, Any]:
    """Writes a key-value pair to the 'custom' section of a server's specific
    JSON configuration file (e.g., ``<server_name>_config.json``).
    This is a sandboxed way for plugins or users to store arbitrary data
    associated with a server. The key will be stored as ``custom.<key>``.

    Args:
        server_name (str): The name of the server.
        key (str): The key (string) for the custom value within the 'custom' section.
            Cannot be empty.
        value (Any): The value to write. Must be JSON serializable.

    Returns:
        Dict[str, Any]: A dictionary containing the operation result.
        On success: ``{"status": "success", "message": "Custom value '<key>' updated..."}``
        On error: ``{"status": "error", "message": "<error_message>"}``

    Raises:
        InvalidServerNameError: If `server_name` is empty.
        MissingArgumentError: If `key` is empty.
        ConfigParseError: If `value` is not JSON serializable.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    if not key:
        raise MissingArgumentError("A 'key' must be provided.")

    logger.info(f"API (Plugin): Writing custom value for '{server_name}': Key='{key}'")
    try:
        server = app_context.get_server(server_name)
        # This method is sandboxed to the 'custom' section
        server.set_custom_config_value(key, value)
        return {
            "status": "success",
            "message": f"Custom value '{key}' updated for server '{server_name}'.",
        }
    except BSMError as e:
        logger.error(
            f"API (Plugin): Error setting custom value for '{server_name}': {e}"
        )
        return {"status": "error", "message": str(e)}
    except Exception as e:
        logger.error(
            f"API (Plugin): Unexpected error setting custom value for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": "An unexpected error occurred."}


@plugin_method("get_all_server_settings")
def get_all_server_settings(
    server_name: str, app_context: AppContext
) -> Dict[str, Any]:
    """Reads the entire JSON configuration for a specific server from its
    dedicated configuration file (e.g., ``<server_name>_config.json``).
    If the file doesn't exist, it will be created with default values.
    Handles schema migration if an older config format is detected.

    Args:
        server_name (str): The name of the server.

    Returns:
        Dict[str, Any]: A dictionary containing the operation result.
        On success: ``{"status": "success", "data": <all_settings_dict>}``
        On error: ``{"status": "error", "message": "<error_message>"}``

    Raises:
        InvalidServerNameError: If `server_name` is empty.
        FileOperationError: If creating/reading the config directory/file fails.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.debug(f"API: Reading all settings for server '{server_name}'.")
    try:
        server = app_context.get_server(server_name)
        # _load_server_config handles loading and migration
        all_settings = server._load_server_config()
        return {"status": "success", "data": all_settings}
    except BSMError as e:
        logger.error(f"API: Error reading all settings for server '{server_name}': {e}")
        return {"status": "error", "message": str(e)}
    except Exception as e:
        logger.error(
            f"API: Unexpected error reading all settings for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": "An unexpected error occurred."}


@plugin_method("start_server")
@trigger_plugin_event(before="before_server_start", after="after_server_start")
def start_server(server_name: str, app_context: AppContext) -> Dict[str, Any]:
    """Starts the specified Bedrock server."""
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.info(f"API: Attempting to start server '{server_name}'...")
    try:
        server = app_context.get_server(server_name)

        if server.is_running():
            logger.warning(
                f"API: Server '{server_name}' is already running. Start request ignored."
            )
            return {
                "status": "error",
                "message": f"Server '{server_name}' is already running.",
            }

        server.start()
        app_context.bedrock_process_manager.add_server(server)
        logger.info(f"API: Start for server '{server_name}' completed.")
        return {
            "status": "success",
            "message": f"Server '{server_name}' process started.",
        }

    except BSMError as e:
        logger.error(f"API: Failed to start server '{server_name}': {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"Failed to start server '{server_name}': {e}",
        }
    except Exception as e:
        logger.error(
            f"API: Unexpected error starting server '{server_name}': {e}", exc_info=True
        )
        return {
            "status": "error",
            "message": f"Unexpected error starting server '{server_name}': {e}",
        }


@plugin_method("stop_server")
@trigger_plugin_event(before="before_server_stop", after="after_server_stop")
def stop_server(server_name: str, app_context: AppContext) -> Dict[str, str]:
    """Stops the specified Bedrock server.

    Triggers the ``before_server_stop`` and ``after_server_stop`` plugin events.
    The method used for stopping :meth:`~.core.bedrock_server.BedrockServer.stop`, which involves gracefully shutdown, with a forceful fallback.

    Args:
        server_name (str): The name of the server to stop.

    Returns:
        Dict[str, str]: A dictionary containing the operation result.

        On success: ``{"status": "success", "message": "Server... stopped successfully."}`` or
                    ``{"status": "success", "message": "Server... stop initiated via <service_manager>."}``

        On error (e.g., already stopped): ``{"status": "error", "message": "<error_message>"}``

    Raises:
        InvalidServerNameError: If `server_name` is not provided.
        ServerStopError: If the server fails to stop after all attempts.
        BSMError: For other application-specific errors during shutdown.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.info(f"API: Attempting to stop server '{server_name}'...")
    server = None
    try:
        server = app_context.get_server(server_name)

        if not server.is_running():
            logger.warning(
                f"API: Server '{server_name}' is not running. Stop request ignored."
            )
            server.set_status_in_config("STOPPED")
            return {
                "status": "error",
                "message": f"Server '{server_name}' was already stopped.",
            }

        server.stop()
        app_context.bedrock_process_manager.remove_server(server.server_name)
        logger.info(f"API: Server '{server_name}' stopped successfully.")
        return {
            "status": "success",
            "message": f"Server '{server_name}' stopped successfully.",
        }
    except BSMError as e:
        logger.error(f"API: Failed to stop server '{server_name}': {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"Failed to stop server '{server_name}': {e}",
        }
    except Exception as e:
        logger.error(
            f"API: Unexpected error stopping server '{server_name}': {e}", exc_info=True
        )
        return {
            "status": "error",
            "message": f"Unexpected error stopping server '{server_name}': {e}",
        }
    finally:
        # Always attempt to clean up the PID file as a final step.
        if server:
            try:
                pid_file_path = server.get_pid_file_path()
                if os.path.isfile(pid_file_path):
                    remove_pid_file_if_exists(pid_file_path)
            except Exception as e_cleanup:
                logger.warning(
                    f"Error during PID file cleanup for '{server_name}': {e_cleanup}"
                )


@plugin_method("restart_server")
def restart_server(
    server_name: str,
    app_context: AppContext,
    send_message: bool = True,
) -> Dict[str, str]:
    """Restarts the specified Bedrock server by orchestrating stop and start.

    This function internally calls :func:`~.stop_server` and then
    :func:`~.start_server`.

    - If the server is already stopped, this function will attempt to start it.
    - If running, it will attempt to stop it (optionally sending a restart
      message to the server if ``send_message=True``), wait briefly for the
      stop to complete, and then start it again.

    Args:
        server_name (str): The name of the server to restart.
        send_message (bool, optional): If ``True``, attempts to send a "say Restarting server..."
            message to the server console via
            :meth:`~.core.bedrock_server.BedrockServer.send_command`
            before stopping. Defaults to ``True``.

    Returns:
        Dict[str, str]: A dictionary with the operation status and a message,
        reflecting the outcome of the start/stop operations.
        On success: ``{"status": "success", "message": "Server... restarted successfully."}``
        On error: ``{"status": "error", "message": "Restart failed: <reason>"}``

    Raises:
        InvalidServerNameError: If `server_name` is not provided.
        ServerStartError: If the start phase fails (from :func:`~.start_server`).
        ServerStopError: If the stop phase fails (from :func:`~.stop_server`).
        BSMError: For other application-specific errors.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.debug(
        f"API: Initiating restart for server '{server_name}'. Send message: {send_message}"
    )
    try:
        server = app_context.get_server(server_name)
        is_running = server.is_running()

        # If server is not running, just start it.
        if not is_running:
            logger.info(
                f"API: Server '{server_name}' was not running. Attempting to start..."
            )
            start_result = start_server(server_name, app_context=app_context)
            if start_result.get("status") == "success":
                start_result["message"] = (
                    f"Server '{server_name}' was not running and has been started."
                )
            return start_result

        # If server is running, perform the stop-start cycle.
        logger.info(
            f"API: Server '{server_name}' is running. Proceeding with stop/start cycle."
        )
        if send_message:
            try:
                server.send_command("say Restarting server...")
            except BSMError as e:
                logger.warning(
                    f"API: Failed to send restart warning to '{server_name}': {e}"
                )

        stop_result = stop_server(server_name, app_context=app_context)
        if stop_result.get("status") == "error":
            stop_result["message"] = (
                f"Restart failed during stop phase: {stop_result.get('message')}"
            )
            return stop_result

        start_result = start_server(server_name, app_context=app_context)
        if start_result.get("status") == "error":
            start_result["message"] = (
                f"Restart failed during start phase: {start_result.get('message')}"
            )
            return start_result

        logger.info(f"API: Server '{server_name}' restarted successfully.")
        return {
            "status": "success",
            "message": f"Server '{server_name}' restarted successfully.",
        }

    except BSMError as e:
        logger.error(
            f"API: Failed to restart server '{server_name}': {e}", exc_info=True
        )
        return {"status": "error", "message": f"Restart failed: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error during restart for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Unexpected error during restart: {e}"}


@plugin_method("send_command")
@trigger_plugin_event(before="before_command_send", after="after_command_send")
def send_command(
    server_name: str, command: str, app_context: AppContext
) -> Dict[str, str]:
    """Sends a command to a running Bedrock server.

    The command is checked against a blacklist (defined by
    :const:`~bedrock_server_manager.config.blocked_commands.API_COMMAND_BLACKLIST`)
    before being sent via
    :meth:`~.core.bedrock_server.BedrockServer.send_command`.
    Triggers ``before_command_send`` and ``after_command_send`` plugin events.

    Args:
        server_name (str): The name of the server to send the command to.
        command (str): The command string to send (e.g., "list", "say Hello").
            Cannot be empty.

    Returns:
        Dict[str, str]: On successful command submission, returns a dictionary:
        ``{"status": "success", "message": "Command '<command>' sent successfully."}``.
        If an error occurs, an exception is raised instead of returning an error dictionary.

    Raises:
        InvalidServerNameError: If `server_name` is not provided.
        MissingArgumentError: If `command` is empty.
        BlockedCommandError: If the command is in the API blacklist.
        ServerNotRunningError: If the target server is not running.
        SendCommandError: For underlying issues during command transmission (e.g., pipe errors).
        ServerError: For other unexpected errors during the operation.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    if not command or not command.strip():
        raise MissingArgumentError("Command cannot be empty.")

    command_clean = command.strip()

    logger.info(
        f"API: Attempting to send command to server '{server_name}': '{command_clean}'"
    )
    try:
        # Check command against the configured blacklist.
        blacklist = API_COMMAND_BLACKLIST or []
        command_check = command_clean.lower().lstrip("/")
        for blocked_cmd_prefix in blacklist:
            if isinstance(blocked_cmd_prefix, str) and command_check.startswith(
                blocked_cmd_prefix.lower()
            ):
                error_msg = f"Command '{command_clean}' is blocked by configuration."
                logger.warning(
                    f"API: Blocked command attempt for '{server_name}': {error_msg}"
                )
                raise BlockedCommandError(error_msg)

        server = app_context.get_server(server_name)
        server.send_command(command_clean)

        logger.info(
            f"API: Command '{command_clean}' sent successfully to server '{server_name}'."
        )
        return {
            "status": "success",
            "message": f"Command '{command_clean}' sent successfully.",
        }

    except BSMError as e:
        logger.error(
            f"API: Failed to send command to server '{server_name}': {e}", exc_info=True
        )
        # Re-raise to allow higher-level handlers to catch specific BSM errors.
        raise
    except Exception as e:
        logger.error(
            f"API: Unexpected error sending command to '{server_name}': {e}",
            exc_info=True,
        )
        # Wrap unexpected errors in a generic ServerError.
        raise ServerError(f"Unexpected error sending command: {e}") from e


@trigger_plugin_event(
    before="before_delete_server_data", after="after_delete_server_data"
)
def delete_server_data(
    server_name: str,
    app_context: AppContext,
    stop_if_running: bool = True,
) -> Dict[str, str]:
    """Deletes all data associated with a Bedrock server.

    .. danger::
        This is a **HIGHLY DESTRUCTIVE** and irreversible operation.

    It calls :meth:`~.core.bedrock_server.BedrockServer.delete_all_data`, which
    removes:
    - The server's main installation directory.
    - The server's JSON configuration subdirectory.
    - The server's entire backup directory.
    - The server's PID file.

    Triggers ``before_delete_server_data`` and ``after_delete_server_data`` plugin events.

    Args:
        server_name (str): The name of the server to delete.
        stop_if_running (bool, optional): If ``True`` (default), the server will be
            stopped using :func:`~.stop_server` before its data is deleted.
            If ``False`` and the server is running, the operation will likely
            fail due to file locks or other conflicts.

    Returns:
        Dict[str, str]: A dictionary with the operation status and a message.
        On success: ``{"status": "success", "message": "All data for server... deleted successfully."}``
        On error: ``{"status": "error", "message": "<error_message>"}``

    Raises:
        InvalidServerNameError: If `server_name` is not provided.
        ServerStopError: If `stop_if_running` is ``True`` and the server fails to stop.
        FileOperationError: If deleting one or more essential directories or files fails.
        BSMError: For other application-specific errors.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    # High-visibility warning for a destructive operation.
    logger.warning(
        f"API: !!! Initiating deletion of ALL data for server '{server_name}'. Stop if running: {stop_if_running} !!!"
    )
    try:
        server = app_context.get_server(server_name)

        # Stop the server first if requested and it's running.
        if stop_if_running and server.is_running():
            logger.info(
                f"API: Server '{server_name}' is running. Stopping before deletion..."
            )

            stop_result = stop_server(server_name, app_context=app_context)
            if stop_result.get("status") == "error":
                error_msg = f"Failed to stop server '{server_name}' before deletion: {stop_result.get('message')}. Deletion aborted."
                logger.error(error_msg)
                return {"status": "error", "message": error_msg}

            logger.info(f"API: Server '{server_name}' stopped.")

        logger.debug(
            f"API: Proceeding with deletion of data for server '{server_name}'..."
        )
        server.delete_all_data()
        logger.info(f"API: Successfully deleted all data for server '{server_name}'.")
        return {
            "status": "success",
            "message": f"All data for server '{server_name}' deleted successfully.",
        }

    except BSMError as e:
        logger.error(
            f"API: Failed to delete server data for '{server_name}': {e}", exc_info=True
        )
        return {"status": "error", "message": f"Failed to delete server data: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error deleting server data for '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Unexpected error deleting server data: {e}",
        }
