import logging
import os
import threading
from typing import Any, Dict, Optional

from ..context import AppContext
from ..error import (
    BSMError,
    FileOperationError,
    InvalidServerNameError,
    MissingArgumentError,
    UserInputError,
)
from ..plugins import plugin_method
from ..plugins.event_trigger import trigger_plugin_event
from .server import server_lifecycle_manager

logger = logging.getLogger(__name__)

_install_update_lock = threading.RLock()


@plugin_method("install_new_server")
@trigger_plugin_event(before="before_server_install", after="after_server_install")
def install_new_server(
    server_name: str,
    app_context: AppContext,
    target_version: str = "LATEST",
    server_zip_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Installs a new server instance.

    Args:
        server_name (str): The name for the new server.
        app_context (AppContext): The application context.
        target_version (str, optional): The target version to install (default: "LATEST").
        server_zip_path (Optional[str], optional): Path to a local zip file for installation.

    Returns:
        Dict[str, Any]: A dictionary containing the installation status and message.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")

    try:
        from ..utils.server import core_validate_server_name_format

        core_validate_server_name_format(server_name)

        settings = app_context.settings

        base_dir = settings.get("paths.servers")
        if not base_dir:
            raise FileOperationError("'paths.servers' not configured in settings.")
        if os.path.exists(os.path.join(base_dir, server_name)):
            raise UserInputError(
                f"Directory for server '{server_name}' already exists."
            )

        logger.info(
            f"API: Installing new server '{server_name}', target version '{target_version}'."
        )
        server = app_context.get_server(server_name)
        server.install_or_update(target_version, server_zip_path=server_zip_path)
        return {
            "status": "success",
            "version": server.get_version(),
            "message": f"Server '{server_name}' installed successfully to version {server.get_version()}.",
        }

    except BSMError as e:
        logger.error(
            f"API: Installation failed for '{server_name}': {e}", exc_info=True
        )
        return {"status": "error", "message": f"Server installation failed: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error installing '{server_name}': {e}", exc_info=True
        )
        return {"status": "error", "message": f"An unexpected error occurred: {e}"}


@plugin_method("update_server")
@trigger_plugin_event(before="before_server_update", after="after_server_update")
def update_server(
    server_name: str,
    app_context: AppContext,
    send_message: bool = True,
) -> Dict[str, Any]:
    """Updates an existing server instance.

    Args:
        server_name (str): The name of the server to update.
        app_context (AppContext): The application context.
        send_message (bool, optional): Whether to send a message to players before updating.

    Returns:
        Dict[str, Any]: A dictionary containing the update status, a boolean flag `updated`,
        and a message.
    """
    if not _install_update_lock.acquire(timeout=300):
        logger.warning(
            f"An install/update operation for '{server_name}' is already in progress. Skipping."
        )
        return {
            "status": "skipped",
            "message": "An install/update operation is already in progress.",
        }

    try:
        if not server_name:
            raise InvalidServerNameError("Server name cannot be empty.")

        server = app_context.get_server(server_name)
        target_version = server.get_target_version()

        logger.info(
            f"API: Updating server '{server_name}'. Send message: {send_message}"
        )
        if not server.is_update_needed(target_version):
            return {
                "status": "success",
                "updated": False,
                "message": "Server is already up-to-date.",
            }

        with server_lifecycle_manager(
            server_name,
            stop_before=True,
            start_after=True,
            restart_on_success_only=True,
            app_context=app_context,
        ):
            logger.info(f"API: Backing up '{server_name}' before update...")
            server.backup_all_data()
            logger.info(
                f"API: Performing update for '{server_name}' to target '{target_version}'..."
            )
            server.install_or_update(target_version)

        return {
            "status": "success",
            "updated": True,
            "new_version": server.get_version(),
            "message": f"Server '{server_name}' updated successfully to {server.get_version()}.",
        }

    except BSMError as e:
        logger.error(f"API: Update failed for '{server_name}': {e}", exc_info=True)
        return {"status": "error", "message": f"Server update failed: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error updating '{server_name}': {e}", exc_info=True
        )
        return {"status": "error", "message": f"An unexpected error occurred: {e}"}
    finally:
        _install_update_lock.release()
