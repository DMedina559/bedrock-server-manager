# bedrock_server_manager/api/world.py
"""Provides API functions for managing Bedrock server worlds.

This module offers a high-level interface for world-related operations on
Bedrock server instances. It wraps methods of the
:class:`~bedrock_server_manager.core.bedrock_server.BedrockServer` class
to facilitate tasks such as:

    - Retrieving the active world name (:func:`~.get_world_name`).
    - Exporting the active server world to a ``.mcworld`` archive file
      (:func:`~.export_world`).
    - Importing a world from a ``.mcworld`` file, replacing the active world
      (:func:`~.import_world`).
    - Resetting the active server world, prompting regeneration on next start
      (:func:`~.reset_world`).

Operations involving world file modifications (export, import, reset) are
thread-safe using a unified lock (``_world_lock``) to prevent data corruption.
For actions that require the server to be offline (like import or reset),
this module utilizes the
:func:`~bedrock_server_manager.api.utils.server_lifecycle_manager`
to safely stop and restart the server. All functions are exposed to the
plugin system.
"""

import os
import logging
import threading
from typing import Dict, Optional, Any

# Plugin system imports to bridge API functionality.
from ..plugins import plugin_method

# Local application imports.
from .utils import server_lifecycle_manager
from ..error import (
    BSMError,
    InvalidServerNameError,
    FileOperationError,
    MissingArgumentError,
)
from bedrock_server_manager.utils.general import get_timestamp
from ..context import AppContext

logger = logging.getLogger(__name__)

# A unified lock to prevent race conditions during any world file operation
# (export, import, reset). This ensures data integrity.
_world_lock = threading.Lock()


@plugin_method("get_world_name")
def get_world_name(server_name: str, app_context: AppContext) -> Dict[str, Any]:
    """Retrieves the configured world name (`level-name`) for a server.

    This function reads the `server.properties` file to get the name of the
    directory where the world data is stored, by calling
    :meth:`~.core.bedrock_server.BedrockServer.get_world_name`.

    Args:
        server_name (str): The name of the server to query.

    Returns:
        Dict[str, Any]: A dictionary with the operation result.
        On success: ``{"status": "success", "world_name": "<world_name_str>"}``.
        On error: ``{"status": "error", "message": "<error_message>"}``.

    Raises:
        InvalidServerNameError: If `server_name` is not provided.
        BSMError: Can be raised by
            :class:`~.core.bedrock_server.BedrockServer` instantiation or by
            the underlying `get_world_name` method (e.g.,
            :class:`~.error.AppFileNotFoundError` if ``server.properties`` is missing,
            or :class:`~.error.ConfigParseError` if ``level-name`` is missing or malformed).
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")

    logger.debug(f"API: Attempting to get world name for server '{server_name}'...")
    try:
        server = app_context.get_server(server_name)
        world_name_str = server.get_world_name()
        logger.info(
            f"API: Retrieved world name for '{server_name}': '{world_name_str}'"
        )
        return {"status": "success", "world_name": world_name_str}
    except BSMError as e:
        logger.error(
            f"API: Failed to get world name for '{server_name}': {e}", exc_info=True
        )
        return {"status": "error", "message": f"Failed to get world name: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error getting world name for '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Unexpected error getting world name: {e}",
        }


from ..plugins.event_trigger import trigger_plugin_event


@plugin_method("export_world")
@trigger_plugin_event(before="before_world_export", after="after_world_export")
def export_world(
    server_name: str,
    app_context: AppContext,
    export_dir: Optional[str] = None,
    stop_start_server: bool = True,
) -> Dict[str, Any]:
    """Exports the server's currently active world to a .mcworld archive.

    This operation is thread-safe due to ``_world_lock``. If `stop_start_server`
    is ``True``, it uses the
    :func:`~bedrock_server_manager.api.utils.server_lifecycle_manager` to ensure
    the server is stopped during the export for file consistency, and then
    restarted. The core world export is performed by
    :meth:`~.core.bedrock_server.BedrockServer.export_world_directory_to_mcworld`.
    Triggers ``before_world_export`` and ``after_world_export`` plugin events.

    Args:
        server_name (str): The name of the server whose world is to be exported.
        export_dir (Optional[str], optional): The directory to save the exported
            ``.mcworld`` file. If ``None``, it defaults to a "worlds" subdirectory
            within the application's global content directory (defined by
            ``paths.content`` setting). Defaults to ``None``.
        stop_start_server (bool, optional): If ``True``, the server will be
            stopped before the export and restarted afterwards. Defaults to ``True``.

    Returns:
        Dict[str, Any]: A dictionary with the operation result.
        Possible statuses: "success", "error", or "skipped" (if lock not acquired).
        On success: ``{"status": "success", "export_file": "<path_to_mcworld>", "message": "World '<name>' exported..."}``
        On error: ``{"status": "error", "message": "<error_message>"}``.

    Raises:
        InvalidServerNameError: If `server_name` is empty.
        FileOperationError: If the content directory setting (``paths.content``)
            is missing when `export_dir` is ``None``, or for other file I/O errors
            during export or lifecycle management.
        BSMError: Propagates errors from underlying operations, including
            :class:`~.error.AppFileNotFoundError` if world directory is missing,
            :class:`~.error.BackupRestoreError` from export, or errors from server stop/start.
    """
    if not _world_lock.acquire(blocking=False):
        logger.warning(
            f"A world operation for '{server_name}' is already in progress. Skipping concurrent export."
        )
        return {
            "status": "skipped",
            "message": "A world operation is already in progress.",
        }

    try:
        if not server_name:
            raise InvalidServerNameError("Server name cannot be empty.")

        # Determine the effective export directory before triggering hooks.
        if export_dir:
            effective_export_dir = export_dir
        else:
            settings = app_context.settings
            content_base_dir = settings.get("paths.content")
            if not content_base_dir:
                raise FileOperationError(
                    "CONTENT_DIR setting missing for default export directory."
                )
            effective_export_dir = os.path.join(content_base_dir, "worlds")

        logger.info(
            f"API: Initiating world export for '{server_name}' (Stop/Start: {stop_start_server})"
        )

        try:
            server = app_context.get_server(server_name)

            os.makedirs(effective_export_dir, exist_ok=True)
            world_name_str = server.get_world_name()
            timestamp = get_timestamp()
            export_filename = f"{world_name_str}_export_{timestamp}.mcworld"
            export_file_path = os.path.join(effective_export_dir, export_filename)

            # Use the lifecycle manager to handle stopping and starting the server.
            with server_lifecycle_manager(
                server_name, stop_before=stop_start_server, app_context=app_context
            ):
                logger.info(
                    f"API: Exporting world '{world_name_str}' to '{export_file_path}'..."
                )
                server.export_world_directory_to_mcworld(
                    world_name_str, export_file_path
                )

            logger.info(
                f"API: World for server '{server_name}' exported to '{export_file_path}'."
            )
            return {
                "status": "success",
                "export_file": export_file_path,
                "message": f"World '{world_name_str}' exported successfully to {export_filename}.",
            }

        except (BSMError, ValueError) as e:
            logger.error(
                f"API: Failed to export world for '{server_name}': {e}", exc_info=True
            )
            return {"status": "error", "message": f"Failed to export world: {e}"}
        except Exception as e:
            logger.error(
                f"API: Unexpected error exporting world for '{server_name}': {e}",
                exc_info=True,
            )
            return {
                "status": "error",
                "message": f"Unexpected error exporting world: {e}",
            }

    finally:
        _world_lock.release()


@plugin_method("import_world")
@trigger_plugin_event(before="before_world_import", after="after_world_import")
def import_world(
    server_name: str,
    selected_file_path: str,
    app_context: AppContext,
    stop_start_server: bool = True,
) -> Dict[str, str]:
    """Imports a world from a .mcworld file, replacing the active world.

    This is a destructive operation that replaces the current world. It is
    thread-safe and manages the server lifecycle to ensure data integrity.

    .. warning::
        This is a **DESTRUCTIVE** operation. The existing active world directory
        will be deleted before the new world is imported.

    If `stop_start_server` is ``True``, this function uses the
    :func:`~bedrock_server_manager.api.utils.server_lifecycle_manager` to ensure
    the server is stopped during the import. The core world import is performed by
    :meth:`~.core.bedrock_server.BedrockServer.import_active_world_from_mcworld`.
    Triggers ``before_world_import`` and ``after_world_import`` plugin events.

    Args:
        server_name (str): The name of the server to import the world into.
        selected_file_path (str): The absolute path to the ``.mcworld`` file to import.
        stop_start_server (bool, optional): If ``True``, the server will be
            stopped before the import and restarted afterwards. Defaults to ``True``.

    Returns:
        Dict[str, str]: A dictionary with the operation result.
        Possible statuses: "success", "error", or "skipped" (if lock not acquired).
        On success: ``{"status": "success", "message": "World '<name>' imported..."}``
        On error: ``{"status": "error", "message": "<error_message>"}``.

    Raises:
        InvalidServerNameError: If `server_name` is empty.
        MissingArgumentError: If `selected_file_path` is empty.
        FileNotFoundError: If `selected_file_path` does not exist (from implementation).
        BSMError: Propagates errors from underlying operations, including
            :class:`~.error.BackupRestoreError` from import, :class:`~.error.ExtractError`,
            or errors from server stop/start.
    """
    if not _world_lock.acquire(blocking=False):
        logger.warning(
            f"A world operation for '{server_name}' is already in progress. Skipping concurrent import."
        )
        return {
            "status": "skipped",
            "message": "A world operation is already in progress.",
        }

    try:
        if not server_name:
            raise InvalidServerNameError("Server name cannot be empty.")
        if not selected_file_path:
            raise MissingArgumentError(".mcworld file path cannot be empty.")

        selected_filename = os.path.basename(selected_file_path)
        logger.info(
            f"API: Initiating world import for '{server_name}' from '{selected_filename}' (Stop/Start: {stop_start_server})"
        )

        try:
            server = app_context.get_server(server_name)
            if not os.path.isfile(selected_file_path):
                raise FileNotFoundError(
                    f"Source .mcworld file not found: {selected_file_path}"
                )

            imported_world_name: Optional[str] = None
            # Use the lifecycle manager to ensure the server is stopped during the import.
            with server_lifecycle_manager(
                server_name, stop_before=stop_start_server, app_context=app_context
            ):
                logger.info(
                    f"API: Importing world from '{selected_filename}' into server '{server_name}'..."
                )
                imported_world_name = server.import_active_world_from_mcworld(
                    selected_file_path
                )

            logger.info(
                f"API: World import from '{selected_filename}' for server '{server_name}' completed."
            )
            return {
                "status": "success",
                "message": f"World '{imported_world_name or 'Unknown'}' imported successfully from {selected_filename}.",
            }

        except (BSMError, FileNotFoundError) as e:
            logger.error(
                f"API: Failed to import world for '{server_name}': {e}", exc_info=True
            )
            return {"status": "error", "message": f"Failed to import world: {e}"}
        except Exception as e:
            logger.error(
                f"API: Unexpected error importing world for '{server_name}': {e}",
                exc_info=True,
            )
            return {
                "status": "error",
                "message": f"Unexpected error importing world: {e}",
            }

    finally:
        _world_lock.release()


@plugin_method("reset_world")
@trigger_plugin_event(before="before_world_reset", after="after_world_reset")
def reset_world(server_name: str, app_context: AppContext) -> Dict[str, str]:
    """Resets the server's world by deleting the active world directory.

    This is a destructive action. Upon next start, the server will generate
    a new world based on its `server.properties` configuration. This function
    is thread-safe and manages the server lifecycle.

    .. warning::
        This is a **DESTRUCTIVE** operation. The existing active world directory
        will be permanently removed.

    This function uses the
    :func:`~bedrock_server_manager.api.utils.server_lifecycle_manager` to ensure
    the server is stopped before deleting the world and restarted afterwards (which
    will trigger new world generation). The active world directory is deleted using
    :meth:`~.core.bedrock_server.BedrockServer.delete_active_world_directory`.
    Triggers ``before_world_reset`` and ``after_world_reset`` plugin events.

    Args:
        server_name (str): The name of the server whose world is to be reset.

    Returns:
        Dict[str, str]: A dictionary with the operation result.
        Possible statuses: "success", "error", or "skipped" (if lock not acquired).
        On success: ``{"status": "success", "message": "World '<name>' reset successfully."}``
        On error: ``{"status": "error", "message": "<error_message>"}``.

    Raises:
        InvalidServerNameError: If `server_name` is empty.
        BSMError: Propagates errors from underlying operations, including
            :class:`~.error.FileOperationError` from deletion, errors determining
            the world name, or errors from server stop/start.
    """
    if not _world_lock.acquire(blocking=False):
        logger.warning(
            f"A world operation for '{server_name}' is already in progress. Skipping concurrent reset."
        )
        return {
            "status": "skipped",
            "message": "A world operation is already in progress.",
        }

    try:
        if not server_name:
            raise InvalidServerNameError("Server name cannot be empty for API request.")

        logger.info(f"API: Initiating world reset for server '{server_name}'...")

        try:
            server = app_context.get_server(server_name)
            world_name_for_msg = server.get_world_name()

            # The lifecycle manager ensures the server is stopped, the world is deleted,
            # and the server is restarted (which will generate the new world).
            with server_lifecycle_manager(
                server_name,
                stop_before=True,
                start_after=True,
                restart_on_success_only=True,
                app_context=app_context,
            ):
                logger.info(
                    f"API: Attempting to delete world directory for world '{world_name_for_msg}'..."
                )
                server.delete_active_world_directory()

            logger.info(
                f"API: World '{world_name_for_msg}' for server '{server_name}' has been successfully reset."
            )
            return {
                "status": "success",
                "message": f"World '{world_name_for_msg}' reset successfully.",
            }

        except BSMError as e:
            logger.error(
                f"API: Failed to reset world for '{server_name}': {e}", exc_info=True
            )
            return {"status": "error", "message": f"Failed to reset world: {e}"}
        except Exception as e:
            logger.error(
                f"API: Unexpected error resetting world for '{server_name}': {e}",
                exc_info=True,
            )
            return {
                "status": "error",
                "message": f"An unexpected error occurred while resetting the world: {e}",
            }

    finally:
        _world_lock.release()
