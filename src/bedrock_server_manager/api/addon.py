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

import logging
import os
import threading
from typing import Any, Dict

from ..context import AppContext
from ..error import (
    AppFileNotFoundError,
    BSMError,
    MissingArgumentError,
    SendCommandError,
    ServerNotRunningError,
)

# Plugin system imports to bridge API functionality.
from ..plugins import plugin_method
from ..plugins.event_trigger import trigger_plugin_event

# Local application imports.
from .utils import server_lifecycle_manager

logger = logging.getLogger(__name__)

# A unified lock to prevent race conditions during addon file operations.
# This ensures that only one addon installation can occur at a time,
# preventing potential file corruption.
_addon_lock = threading.Lock()


@plugin_method("import_addon")
@trigger_plugin_event(before="before_addon_import", after="after_addon_import")
def import_addon(  # noqa: C901
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


@plugin_method("list_world_addons")
def list_world_addons(server_name: str, app_context: AppContext) -> Dict[str, Any]:
    """Lists all addons for a server's active world.

    Args:
        server_name (str): The name of the server.
        app_context (AppContext): The application context.

    Returns:
        Dict[str, Any]: A dictionary containing the addon lists.
    """
    server = app_context.get_server(server_name)
    return {"status": "success", "addons": server.list_world_addons()}


@plugin_method("enable_addon")
@trigger_plugin_event(before="before_addon_enable", after="after_addon_enable")
def enable_addon(
    server_name: str,
    pack_uuid: str,
    pack_type: str,
    app_context: AppContext,
) -> Dict[str, str]:
    """Enables a disabled addon for a server's active world.

    Args:
        server_name (str): The name of the server.
        pack_uuid (str): The UUID of the pack to enable.
        pack_type (str): The type of the pack.
        app_context (AppContext): The application context.

    Returns:
        Dict[str, str]: Status of the operation.
    """
    if not _addon_lock.acquire(blocking=False):
        return {
            "status": "skipped",
            "message": "An addon operation is already in progress.",
        }

    try:
        server = app_context.get_server(server_name)
        with server_lifecycle_manager(
            server_name,
            stop_before=True,
            start_after=True,
            restart_on_success_only=True,
            app_context=app_context,
        ):
            server.enable_addon(pack_uuid=pack_uuid, pack_type=pack_type)
        return {
            "status": "success",
            "message": f"Successfully enabled pack '{pack_uuid}'.",
        }
    except BSMError as e:
        logger.error(
            f"API: Error enabling addon '{pack_uuid}' on '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": str(e)}
    except Exception as e:
        logger.error(
            f"API: Unexpected error enabling addon '{pack_uuid}' on '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": str(e)}
    finally:
        _addon_lock.release()


@plugin_method("disable_addon")
@trigger_plugin_event(before="before_addon_disable", after="after_addon_disable")
def disable_addon(
    server_name: str,
    pack_uuid: str,
    pack_type: str,
    app_context: AppContext,
) -> Dict[str, str]:
    """Disables an active addon for a server's active world, preserving files.

    Args:
        server_name (str): The name of the server.
        pack_uuid (str): The UUID of the pack to disable.
        pack_type (str): The type of the pack.
        app_context (AppContext): The application context.

    Returns:
        Dict[str, str]: Status of the operation.
    """
    if not _addon_lock.acquire(blocking=False):
        return {
            "status": "skipped",
            "message": "An addon operation is already in progress.",
        }

    try:
        server = app_context.get_server(server_name)
        with server_lifecycle_manager(
            server_name,
            stop_before=True,
            start_after=True,
            restart_on_success_only=True,
            app_context=app_context,
        ):
            server.disable_addon(pack_uuid=pack_uuid, pack_type=pack_type)
        return {
            "status": "success",
            "message": f"Successfully disabled pack '{pack_uuid}'.",
        }
    except BSMError as e:
        logger.error(
            f"API: Error disabling addon '{pack_uuid}' on '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": str(e)}
    except Exception as e:
        logger.error(
            f"API: Unexpected error disabling addon '{pack_uuid}' on '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": str(e)}
    finally:
        _addon_lock.release()


@plugin_method("update_addon_subpack")
@trigger_plugin_event(
    before="before_addon_subpack_update", after="after_addon_subpack_update"
)
def update_addon_subpack(
    server_name: str,
    pack_uuid: str,
    pack_type: str,
    subpack_name: str,
    app_context: AppContext,
) -> Dict[str, str]:
    """Updates the active subpack for an addon on a server's active world.

    Args:
        server_name (str): The name of the server.
        pack_uuid (str): The UUID of the pack.
        pack_type (str): The type of the pack.
        subpack_name (str): The folder name of the target subpack.
        app_context (AppContext): The application context.

    Returns:
        Dict[str, str]: Status of the operation.
    """
    if not _addon_lock.acquire(blocking=False):
        return {
            "status": "skipped",
            "message": "An addon operation is already in progress.",
        }

    try:
        server = app_context.get_server(server_name)
        with server_lifecycle_manager(
            server_name,
            stop_before=True,
            start_after=True,
            restart_on_success_only=True,
            app_context=app_context,
        ):
            server.update_addon_subpack(
                pack_uuid=pack_uuid, pack_type=pack_type, subpack_name=subpack_name
            )
        return {
            "status": "success",
            "message": f"Successfully updated subpack for pack '{pack_uuid}'.",
        }
    except BSMError as e:
        logger.error(
            f"API: Error updating subpack for addon '{pack_uuid}' on '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": str(e)}
    except Exception as e:
        logger.error(
            f"API: Unexpected error updating subpack for addon '{pack_uuid}' on '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": str(e)}
    finally:
        _addon_lock.release()


@plugin_method("uninstall_addon")
@trigger_plugin_event(before="before_addon_uninstall", after="after_addon_uninstall")
def uninstall_addon(
    server_name: str,
    pack_uuid: str,
    pack_type: str,
    app_context: AppContext,
) -> Dict[str, str]:
    """Uninstalls an addon for a server's active world, deleting its files.

    Args:
        server_name (str): The name of the server.
        pack_uuid (str): The UUID of the pack to uninstall.
        pack_type (str): The type of the pack.
        app_context (AppContext): The application context.

    Returns:
        Dict[str, str]: Status of the operation.
    """
    if not _addon_lock.acquire(blocking=False):
        return {
            "status": "skipped",
            "message": "An addon operation is already in progress.",
        }

    try:
        server = app_context.get_server(server_name)
        with server_lifecycle_manager(
            server_name,
            stop_before=True,
            start_after=True,
            restart_on_success_only=True,
            app_context=app_context,
        ):
            server.remove_addon(pack_uuid=pack_uuid, pack_type=pack_type)
        return {
            "status": "success",
            "message": f"Successfully uninstalled pack '{pack_uuid}'.",
        }
    except BSMError as e:
        logger.error(
            f"API: Error uninstalling addon '{pack_uuid}' on '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": str(e)}
    except Exception as e:
        logger.error(
            f"API: Unexpected error uninstalling addon '{pack_uuid}' on '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": str(e)}
    finally:
        _addon_lock.release()


@plugin_method("reorder_addons")
@trigger_plugin_event(before="before_addon_reorder", after="after_addon_reorder")
def reorder_addons(
    server_name: str,
    uuids: list[str],
    pack_type: str,
    app_context: AppContext,
) -> Dict[str, str]:
    """Reorders the active addons for a server's active world.

    Args:
        server_name (str): The name of the server.
        uuids (list[str]): The exact list of active UUIDs in their new order.
        pack_type (str): The type of the pack.
        app_context (AppContext): The application context.

    Returns:
        Dict[str, str]: Status of the operation.
    """
    if not _addon_lock.acquire(blocking=False):
        return {
            "status": "skipped",
            "message": "An addon operation is already in progress.",
        }

    try:
        server = app_context.get_server(server_name)
        with server_lifecycle_manager(
            server_name,
            stop_before=True,
            start_after=True,
            restart_on_success_only=True,
            app_context=app_context,
        ):
            server.reorder_addons(uuids=uuids, pack_type=pack_type)
        return {
            "status": "success",
            "message": f"Successfully reordered {pack_type} packs.",
        }
    except BSMError as e:
        logger.error(
            f"API: Error reordering addons on '{server_name}': {e}", exc_info=True
        )
        return {"status": "error", "message": str(e)}
    except Exception as e:
        logger.error(
            f"API: Unexpected error reordering addons on '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": str(e)}
    finally:
        _addon_lock.release()
