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

import os
import logging
from typing import Dict, Any
import platform
import time
import shutil
import subprocess

# Guarded import for Windows-specific functionality
if platform.system() == "Windows":
    try:
        import win32serviceutil

        PYWIN32_AVAILABLE = True
    except ImportError:
        PYWIN32_AVAILABLE = False
else:
    PYWIN32_AVAILABLE = False


# Plugin system imports to bridge API functionality.
from bedrock_server_manager import plugin_manager
from bedrock_server_manager.plugins.api_bridge import plugin_method

# Local application imports.
from bedrock_server_manager.core.bedrock_server import BedrockServer
from bedrock_server_manager.config.const import EXPATH
from bedrock_server_manager.config.blocked_commands import API_COMMAND_BLACKLIST
from bedrock_server_manager.core.system import process as system_process
from bedrock_server_manager.error import (
    BSMError,
    InvalidServerNameError,
    FileError,
    UserInputError,
    ServerError,
    BlockedCommandError,
    MissingArgumentError,
)

logger = logging.getLogger(__name__)


@plugin_method("get_server_setting")
def get_server_setting(server_name: str, key: str) -> Dict[str, Any]:
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
        server = BedrockServer(server_name)
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


def set_server_setting(server_name: str, key: str, value: Any) -> Dict[str, Any]:
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
        server = BedrockServer(server_name)
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
def set_server_custom_value(server_name: str, key: str, value: Any) -> Dict[str, Any]:
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
        server = BedrockServer(server_name)
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
def get_all_server_settings(server_name: str) -> Dict[str, Any]:
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
        server = BedrockServer(server_name)
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
def start_server(
    server_name: str,
    mode: str = "direct",
) -> Dict[str, Any]:
    """Starts the specified Bedrock server.

    Triggers the ``before_server_start`` and ``after_server_start`` plugin events.
    Manages platform-specific start methods:

    -   **direct**: Runs the server directly in the current process via
        :meth:`~.core.bedrock_server.BedrockServer.start`. This is a blocking
        call until the server stops.
    -   **detached**: Attempts to start the server in the background. It prioritizes
        using the OS-native service manager (systemd on Linux, Windows Services on
        Windows) if a service for this server is configured and active. If a
        service is not used or fails, it falls back to launching a new,
        independent background process via
        :func:`~.core.system.process.launch_detached_process`.

    Args:
        server_name (str): The name of the server to start.
        mode (str, optional): The start mode. Can be 'direct' or 'detached'.
            Defaults to 'direct'.

    Returns:
        Dict[str, Any]: A dictionary containing the operation result.
        - If direct mode: ``{"status": "success", "message": "Server... (direct mode) process finished."}``
        - If detached via service: ``{"status": "success", "message": "Server... started via <service_manager>."}``
        - If detached via fallback: ``{"status": "success", "message": "Server... start initiated... (Launcher PID: <pid>).", "pid": <pid>}``
        - On error: ``{"status": "error", "message": "<error_message>"}``

    Raises:
        InvalidServerNameError: If `server_name` is not provided.
        UserInputError: If `mode` is invalid (not 'direct' or 'detached').
        ServerStartError: If the server is not installed, already running, or if
            :meth:`~.core.bedrock_server.BedrockServer.start` (in direct mode)
            encounters an issue.
        BSMError: For other application-specific errors during startup.
    """
    mode = mode.lower()

    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    if mode not in ["direct", "detached"]:
        raise UserInputError(
            f"Invalid start mode '{mode}'. Must be 'direct' or 'detached'."
        )

    # --- Plugin Hook ---
    plugin_manager.trigger_guarded_event(
        "before_server_start", server_name=server_name, mode=mode
    )

    logger.info(f"API: Attempting to start server '{server_name}' in '{mode}' mode...")
    result = {}
    try:
        server = BedrockServer(server_name)

        if server.is_running():
            logger.warning(
                f"API: Server '{server_name}' is already running. Start request ignored."
            )
            return {
                "status": "error",
                "message": f"Server '{server_name}' is already running.",
            }

        if mode == "direct":
            logger.debug(
                f"API: Calling server.start() for '{server_name}' (direct mode)."
            )
            server.start()  # This is a blocking call.
            logger.info(f"API: Direct start for server '{server_name}' completed.")
            result = {
                "status": "success",
                "message": f"Server '{server_name}' (direct mode) process finished.",
            }
            return result
        elif mode == "detached":
            use_service_manager = False

            # --- OS-Specific Service Start (Preferred Method) ---
            if platform.system() == "Linux" and server.check_service_exists():
                logger.debug(f"API: Using systemd to start server '{server_name}'.")
                systemctl_cmd_path = shutil.which("systemctl")
                if systemctl_cmd_path:
                    try:
                        subprocess.run(
                            [
                                systemctl_cmd_path,
                                "--user",
                                "start",
                                server.systemd_service_name_full,
                            ],
                            check=True,
                            capture_output=True,
                            text=True,
                        )
                        use_service_manager = True
                        result = {
                            "status": "success",
                            "message": f"Server '{server_name}' started via systemd.",
                        }
                    except subprocess.CalledProcessError as e:
                        logger.warning(
                            f"systemd service '{server.systemd_service_name_full}' failed to start: {e.stderr.strip()}. "
                            "Falling back to generic detached process."
                        )
                else:
                    logger.warning(
                        "'systemctl' command not found, falling back to generic detached process."
                    )
            elif (
                platform.system() == "Windows"
                and PYWIN32_AVAILABLE
                and server.check_service_exists()
            ):
                logger.debug(f"API: Using Windows Service to start '{server_name}'.")
                try:
                    win32serviceutil.StartService(server.windows_service_name)
                    use_service_manager = True
                    result = {
                        "status": "success",
                        "message": f"Server '{server_name}' started via Windows Service.",
                    }
                except Exception as e:
                    logger.warning(
                        f"Windows service '{server.windows_service_name}' failed to start: {e}. "
                        "Falling back to generic detached process."
                    )

            if use_service_manager:
                return result

            # --- Generic Detached Start (Fallback for All OSes) ---
            logger.info(
                f"API: Starting server '{server_name}' using generic detached process launcher."
            )
            cli_command_parts = [
                EXPATH,
                "server",
                "start",
                "--server",
                server_name,
                "--mode",
                "direct",  # The detached process runs the server directly
            ]
            cli_command_str_list = [os.fspath(part) for part in cli_command_parts]
            launcher_pid_file_path = system_process.get_bedrock_launcher_pid_file_path(
                server.server_name,
                server.server_config_dir,  # Use BedrockServer instance properties
            )

            launcher_pid = system_process.launch_detached_process(
                cli_command_str_list,
                launcher_pid_file_path,  # Pass the launcher PID file path
            )
            logger.info(
                f"API: Detached server starter for '{server_name}' launched with PID {launcher_pid}."
            )
            result = {
                "status": "success",
                "message": f"Server '{server_name}' start initiated in detached mode (Launcher PID: {launcher_pid}).",
                "pid": launcher_pid,
            }
            return result

    except BSMError as e:
        logger.error(f"API: Failed to start server '{server_name}': {e}", exc_info=True)
        result = {
            "status": "error",
            "message": f"Failed to start server '{server_name}': {e}",
        }
        return result
    except Exception as e:
        logger.error(
            f"API: Unexpected error starting server '{server_name}': {e}", exc_info=True
        )
        result = {
            "status": "error",
            "message": f"Unexpected error starting server '{server_name}': {e}",
        }
        return result
    finally:
        # --- Plugin Hook ---
        plugin_manager.trigger_guarded_event(
            "after_server_start", server_name=server_name, result=result
        )


@plugin_method("stop_server")
def stop_server(server_name: str) -> Dict[str, str]:
    """Stops the specified Bedrock server.

    Triggers the ``before_server_stop`` and ``after_server_stop`` plugin events.
    The method prioritizes stopping via the OS-native service manager (systemd on
    Linux, Windows Services on Windows) if the server's service is active.
    If not managed by a service or if service stop fails, it falls back to a
    direct stop attempt using
    :meth:`~.core.bedrock_server.BedrockServer.stop`, which involves sending
    a "stop" command and then potentially forcefully terminating the process.

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

    # --- Plugin Hook ---
    plugin_manager.trigger_guarded_event("before_server_stop", server_name=server_name)

    logger.info(f"API: Attempting to stop server '{server_name}'...")
    result = {}
    try:
        server = BedrockServer(server_name)

        if not server.is_running():
            logger.warning(
                f"API: Server '{server_name}' is not running. Stop request ignored."
            )
            server.set_status_in_config("STOPPED")
            result = {
                "status": "error",
                "message": f"Server '{server_name}' was already stopped.",
            }
            return result

        # --- OS-Specific Service Stop (Preferred Method) ---
        service_stop_initiated = False
        if platform.system() == "Linux" and server.is_service_active():
            logger.debug(f"API: Attempting to stop '{server_name}' using systemd...")
            try:
                systemctl_cmd_path = shutil.which("systemctl")
                subprocess.run(
                    [
                        systemctl_cmd_path,
                        "--user",
                        "stop",
                        server.systemd_service_name_full,
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                service_stop_initiated = True
                result = {
                    "status": "success",
                    "message": f"Server '{server_name}' stop initiated via systemd.",
                }
            except (subprocess.CalledProcessError, FileNotFoundError) as e:
                logger.warning(
                    f"API: Stopping via systemd failed: {e}. Falling back to direct stop."
                )
        elif platform.system() == "Windows" and server.is_service_active():
            logger.debug(
                f"API: Attempting to stop '{server_name}' via Windows Service..."
            )
            try:
                win32serviceutil.StopService(server.windows_service_name)
                service_stop_initiated = True
                result = {
                    "status": "success",
                    "message": f"Server '{server_name}' stop initiated via Windows Service.",
                }
            except Exception as e:
                logger.warning(
                    f"API: Stopping via Windows Service failed: {e}. Falling back to direct stop."
                )
        server.stop()
        logger.info(f"API: Server '{server_name}' stopped successfully.")
        result = {
            "status": "success",
            "message": f"Server '{server_name}' stopped successfully.",
        }

        try:
            launcher_pid_file = system_process.get_bedrock_launcher_pid_file_path(
                server.server_name, server.server_config_dir
            )
            system_process.remove_pid_file_if_exists(launcher_pid_file)
        except Exception as e_launcher_cleanup:
            logger.debug(
                f"Error during launcher PID cleanup for '{server_name}': {e_launcher_cleanup}"
            )

        return result

    except BSMError as e:
        logger.error(f"API: Failed to stop server '{server_name}': {e}", exc_info=True)
        result = {
            "status": "error",
            "message": f"Failed to stop server '{server_name}': {e}",
        }
        return result
    except Exception as e:
        logger.error(
            f"API: Unexpected error stopping server '{server_name}': {e}", exc_info=True
        )
        result = {
            "status": "error",
            "message": f"Unexpected error stopping server '{server_name}': {e}",
        }
        return result
    finally:
        # --- Plugin Hook ---
        plugin_manager.trigger_guarded_event(
            "after_server_stop", server_name=server_name, result=result
        )


@plugin_method("restart_server")
def restart_server(server_name: str, send_message: bool = True) -> Dict[str, str]:
    """Restarts the specified Bedrock server by orchestrating stop and start.

    This function internally calls :func:`~.stop_server` and then
    :func:`~.start_server` (with ``mode="detached"``).

    - If the server is already stopped, this function will attempt to start it
      in 'detached' mode.
    - If running, it will attempt to stop it (optionally sending a restart
      message to the server if ``send_message=True``), wait briefly for the
      stop to complete, and then start it again in 'detached' mode.

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
        server = BedrockServer(server_name)
        is_running = server.is_running()

        # If server is not running, just start it.
        if not is_running:
            logger.info(
                f"API: Server '{server_name}' was not running. Attempting to start..."
            )
            start_result = start_server(server_name, mode="detached")
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

        stop_result = stop_server(server_name)
        if stop_result.get("status") == "error":
            stop_result["message"] = (
                f"Restart failed during stop phase: {stop_result.get('message')}"
            )
            return stop_result

        start_result = start_server(server_name, mode="detached")
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
def send_command(server_name: str, command: str) -> Dict[str, str]:
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

    # --- Plugin Hook ---
    plugin_manager.trigger_event(
        "before_command_send", server_name=server_name, command=command_clean
    )

    logger.info(
        f"API: Attempting to send command to server '{server_name}': '{command_clean}'"
    )
    result = {}
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

        server = BedrockServer(server_name)
        server.send_command(command_clean)

        logger.info(
            f"API: Command '{command_clean}' sent successfully to server '{server_name}'."
        )
        result = {
            "status": "success",
            "message": f"Command '{command_clean}' sent successfully.",
        }
        return result

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
    finally:
        # --- Plugin Hook ---
        plugin_manager.trigger_event(
            "after_command_send",
            server_name=server_name,
            command=command_clean,
            result=result,
        )


def delete_server_data(
    server_name: str, stop_if_running: bool = True
) -> Dict[str, str]:
    """Deletes all data associated with a Bedrock server.

    .. danger::
        This is a **HIGHLY DESTRUCTIVE** and irreversible operation.

    It calls :meth:`~.core.bedrock_server.BedrockServer.delete_all_data`, which
    removes:
    - The server's main installation directory.
    - The server's JSON configuration subdirectory.
    - The server's entire backup directory.
    - The server's systemd user service file (Linux) or Windows Service entry.
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

    # --- Plugin Hook ---
    plugin_manager.trigger_event("before_delete_server_data", server_name=server_name)

    # High-visibility warning for a destructive operation.
    logger.warning(
        f"API: !!! Initiating deletion of ALL data for server '{server_name}'. Stop if running: {stop_if_running} !!!"
    )
    result = {}
    try:
        server = BedrockServer(server_name)

        # Stop the server first if requested and it's running.
        if stop_if_running and server.is_running():
            logger.info(
                f"API: Server '{server_name}' is running. Stopping before deletion..."
            )

            stop_result = stop_server(server_name)
            if stop_result.get("status") == "error":
                error_msg = f"Failed to stop server '{server_name}' before deletion: {stop_result.get('message')}. Deletion aborted."
                logger.error(error_msg)
                result = {"status": "error", "message": error_msg}
                return result

            logger.info(f"API: Server '{server_name}' stopped.")

        # Attempt to remove the associated system service before deleting files.
        if server.check_service_exists():
            logger.info(f"API: Removing system service for '{server_name}'...")
            try:
                server.disable_service()
                server.remove_service()
                logger.info(f"API: System service for '{server_name}' removed.")
            except BSMError as e:
                logger.warning(
                    f"API: Could not remove system service for '{server_name}': {e}. Continuing with data deletion."
                )

        logger.debug(
            f"API: Proceeding with deletion of data for server '{server_name}'..."
        )
        server.delete_all_data()
        logger.info(f"API: Successfully deleted all data for server '{server_name}'.")
        result = {
            "status": "success",
            "message": f"All data for server '{server_name}' deleted successfully.",
        }
        return result

    except BSMError as e:
        logger.error(
            f"API: Failed to delete server data for '{server_name}': {e}", exc_info=True
        )
        result = {"status": "error", "message": f"Failed to delete server data: {e}"}
        return result
    except Exception as e:
        logger.error(
            f"API: Unexpected error deleting server data for '{server_name}': {e}",
            exc_info=True,
        )
        result = {
            "status": "error",
            "message": f"Unexpected error deleting server data: {e}",
        }
        return result
    finally:
        # --- Plugin Hook ---
        plugin_manager.trigger_event(
            "after_delete_server_data", server_name=server_name, result=result
        )
