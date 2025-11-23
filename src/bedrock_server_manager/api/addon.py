# bedrock_server_manager/api/addon.py
"""API functions for managing addons on Bedrock servers.

This module provides a high-level interface for installing and managing addons
(e.g., ``.mcpack``, ``.mcaddon`` files) for specific Bedrock server instances.
It primarily orchestrates calls to the addon processing methods of the
:class:`~bedrock_server_manager.core.bedrock_server.BedrockServer` class.

Currently, the main functionality offered is:
    - Importing and installing addon files into a server's behavior packs and
      resource packs directories via :func:`~.import_addon`.

Operations that modify server files, like addon installation, are designed to be
thread-safe using a lock (``_addon_lock``). The module also utilizes the
:func:`~bedrock_server_manager.api.utils.server_lifecycle_manager` to
optionally manage the server's state (stopping and restarting) during these
operations to ensure data integrity. All primary functions are exposed to the
plugin system.
"""
import os
import logging
import threading
from typing import Dict, Optional

# Plugin system imports to bridge API functionality.
from ..plugins import plugin_method

# Local application imports.
from .utils import server_lifecycle_manager
from ..error import (
    BSMError,
    MissingArgumentError,
    AppFileNotFoundError,
    SendCommandError,
    ServerNotRunningError,
)
from ..context import AppContext

logger = logging.getLogger(__name__)

# A unified lock to prevent race conditions during addon file operations.
# This ensures that only one addon installation can occur at a time,
# preventing potential file corruption.
_addon_lock = threading.Lock()


from ..plugins.event_trigger import trigger_plugin_event


@plugin_method("import_addon")
@trigger_plugin_event(before="before_addon_import", after="after_addon_import")
def import_addon(
    server_name: str,
    addon_file_path: str,
    app_context: AppContext,
    stop_start_server: bool = True,
    restart_only_on_success: bool = True,
) -> Dict[str, str]:
    """Installs an addon to a specified Bedrock server.

    This function handles the import and installation of an addon file
    (.mcaddon or .mcpack) into the server's addon directories. It is
    thread-safe, using a lock to prevent concurrent addon operations which
    could lead to corrupted files. It calls
    :meth:`~.core.bedrock_server.BedrockServer.process_addon_file` for the
    core processing logic.

    The function can optionally manage the server's lifecycle by stopping it
    before the installation and restarting it after, using the
    :func:`~bedrock_server_manager.api.utils.server_lifecycle_manager`.
    Triggers ``before_addon_import`` and ``after_addon_import`` plugin events.

    Args:
        server_name (str): The name of the server to install the addon on.
        addon_file_path (str): The absolute path to the addon file
            (``.mcaddon`` or ``.mcpack``).
        stop_start_server (bool, optional): If ``True``, the server will be stopped
            before installation and started afterward. Defaults to ``True``.
        restart_only_on_success (bool, optional): If ``True`` and `stop_start_server`
            is ``True``, the server will only be restarted if the addon installation
            succeeds. Defaults to ``True``.

    Returns:
        Dict[str, str]: A dictionary with the operation result.
        Possible statuses: "success", "error", or "skipped" (if lock not acquired).
        On success: ``{"status": "success", "message": "Addon '<filename>' installed..."}``
        On error: ``{"status": "error", "message": "<error_message>"}``.

    Raises:
        MissingArgumentError: If `server_name` or `addon_file_path` is not provided.
        AppFileNotFoundError: If the file at `addon_file_path` does not exist.
        InvalidServerNameError: If the server name is not valid (raised from BedrockServer).
        BSMError: Propagates errors from underlying operations, including
            :class:`~.error.UserInputError` (unsupported addon type),
            :class:`~.error.ExtractError`, :class:`~.error.FileOperationError`,
            or errors from server stop/start.
    """
    # Attempt to acquire the lock without blocking. If another addon operation
    # is in progress, skip this one to avoid conflicts.
    if not _addon_lock.acquire(blocking=False):
        logger.warning(
            f"An addon operation for '{server_name}' is already in progress. Skipping concurrent import."
        )
        return {
            "status": "skipped",
            "message": "An addon operation is already in progress.",
        }

    try:
        addon_filename = os.path.basename(addon_file_path) if addon_file_path else "N/A"
        logger.info(
            f"API: Initiating addon import for '{server_name}' from '{addon_filename}'. "
            f"Stop/Start: {stop_start_server}, RestartOnSuccess: {restart_only_on_success}"
        )

        # --- Pre-flight Checks ---
        if not server_name:
            raise MissingArgumentError("Server name cannot be empty.")
        if not addon_file_path:
            raise MissingArgumentError("Addon file path cannot be empty.")
        if not os.path.isfile(addon_file_path):
            raise AppFileNotFoundError(addon_file_path, "Addon file")

        try:
            server = app_context.get_server(server_name)

            # If the server is running, send a warning message to players.
            if server.is_running():
                try:
                    server.send_command("say Installing addon...")
                except (SendCommandError, ServerNotRunningError) as e:
                    logger.warning(
                        f"API: Failed to send addon installation warning to '{server_name}': {e}"
                    )

            # Use a context manager to handle the server's start/stop lifecycle.
            with server_lifecycle_manager(
                server_name,
                stop_before=stop_start_server,
                start_after=stop_start_server,
                restart_on_success_only=restart_only_on_success,
                app_context=app_context,
            ):
                logger.info(
                    f"API: Processing addon file '{addon_filename}' for server '{server_name}'..."
                )
                # Delegate the core file extraction and placement to the server instance.
                server.process_addon_file(addon_file_path)
                logger.info(
                    f"API: Core addon processing completed for '{addon_filename}' on '{server_name}'."
                )

            message = f"Addon '{addon_filename}' installed successfully for server '{server_name}'."
            if stop_start_server:
                message += " Server stop/start cycle handled."
            return {"status": "success", "message": message}

        except BSMError as e:
            # Handle application-specific errors.
            logger.error(
                f"API: Addon import failed for '{addon_filename}' on '{server_name}': {e}",
                exc_info=True,
            )
            return {
                "status": "error",
                "message": f"Error installing addon '{addon_filename}': {e}",
            }

        except Exception as e:
            # Handle any other unexpected errors.
            logger.error(
                f"API: Unexpected error during addon import for '{server_name}': {e}",
                exc_info=True,
            )
            return {
                "status": "error",
                "message": f"Unexpected error installing addon: {e}",
            }

    finally:
        # Ensure the lock is always released, even if errors occur.
        _addon_lock.release()
