# bedrock_server_manager/api/application.py
"""Provides API functions for application-wide information and actions.

This module offers endpoints to retrieve general details about the Bedrock
Server Manager application itself and to perform operations that span across
multiple server instances.

Key functionalities include:
    - Retrieving application metadata (name, version, OS, key directories) via
      :func:`~.get_application_info_api`.
    - Listing globally available content like world templates
      (:func:`~.list_available_worlds_api`) and addons
      (:func:`~.list_available_addons_api`).
    - Aggregating status and version information for all detected server instances
      using :func:`~.get_all_servers_data`.

These functions are exposed to the plugin system via
:func:`~bedrock_server_manager.plugins.api_bridge.plugin_method` and are
intended for use by UIs, CLIs, or other high-level components.
"""

import logging
from typing import Any, Dict

from ..config import const as config_const
from ..context import AppContext
from ..error import BSMError, FileError
from ..plugins import plugin_method
from ..plugins.event_trigger import trigger_plugin_event
from ..utils import list_content_files

logger = logging.getLogger(__name__)


@plugin_method("list_available_worlds_api")
def list_available_worlds_api(app_context: AppContext) -> Dict[str, Any]:
    """Lists available .mcworld files from the content directory.

    Scans the ``worlds`` sub-folder within the application's global content directory.

    Returns:
        Dict[str, Any]: A dictionary with the operation result.
        On success: ``{"status": "success", "files": List[str]}`` where `files` is a
        list of absolute paths to ``.mcworld`` files.
        On error: ``{"status": "error", "message": "<error_message>"}``.

    Raises:
        FileError: If the content directory is not configured or accessible.
    """
    logger.debug("API: Requesting list of available worlds.")
    try:
        content_dir = app_context.settings.get("paths.content")
        worlds = list_content_files(content_dir, "worlds", [".mcworld"])
        return {"status": "success", "files": worlds}
    except FileError as e:
        # Handle specific file-related errors.
        return {"status": "error", "message": str(e)}
    except Exception as e:
        logger.error(f"API: Unexpected error listing worlds: {e}", exc_info=True)
        return {"status": "error", "message": f"Unexpected error: {str(e)}"}


@plugin_method("get_all_servers_data")
def get_all_servers_data(app_context: AppContext) -> Dict[str, Any]:
    """Retrieves status and version for all detected servers.

    This function acts as an API orchestrator to gather data from all individual
    server instances. It can handle
    partial failures, where data for some servers is retrieved successfully
    while others fail (errors for individual servers are included in the message).
    The status of each server is also reconciled with its live state during this call.

    Returns:
        Dict[str, Any]: A dictionary with the operation result.

        On full success (all servers processed without error):
          ``{"status": "success", "servers": List[ServerDataDict]}``
        On partial success (some individual server errors occurred during scan):
          ``{"status": "success", "servers": List[ServerDataDict], "message": "Completed with errors: <details>"}``
          The ``servers`` list contains data for successfully processed servers.
        On total failure (e.g., cannot access base server directory):
          ``{"status": "error", "message": "<error_message>"}``

        Each ``ServerDataDict`` contains keys like "name", "status", "version".

    Raises:
        BSMError: If there's a fundamental issue accessing the base server
            directory (e.g., :class:`~.error.AppFileNotFoundError`).
    """
    logger.debug("API: Getting status for all servers...")
    from ..utils import server as server_utils

    try:
        # Call the core function which returns both data and potential errors.
        servers_data, bsm_error_messages = server_utils.get_servers_data(
            app_context=app_context
        )

        # Check if the core layer collected any individual server errors.
        if bsm_error_messages:
            # Log each individual error for detailed debugging.
            for err_msg in bsm_error_messages:
                logger.error(
                    f"API: Individual server error during get_all_servers_data: {err_msg}"
                )
            # Return a partial success response.
            return {
                "status": "success",
                "servers": servers_data,
                "message": f"Completed with errors: {'; '.join(bsm_error_messages)}",
            }

        # If there were no errors, return a full success response.
        return {"status": "success", "servers": servers_data}

    except BSMError as e:  # Catch setup or I/O errors from the manager.
        logger.error(
            f"API: Setup or I/O error in get_all_servers_data: {e}", exc_info=True
        )
        return {
            "status": "error",
            "message": f"Error accessing directories or configuration: {e}",
        }
    except Exception as e:  # Catch any other unexpected errors.
        logger.error(
            f"API: Unexpected error in get_all_servers_data: {e}", exc_info=True
        )
        return {"status": "error", "message": f"An unexpected error occurred: {e}"}


@plugin_method("get_system_and_app_info")
def get_system_and_app_info(app_context: AppContext) -> Dict[str, Any]:
    """Retrieves basic system and application information.

    Uses global settings to get OS type and app version.

    Returns:
        Dict[str, Any]: On success: ``{"status": "success", "os_type": "...", "app_version": "...", "splash_text": "..."}``.
        On error: ``{"status": "error", "message": "An unexpected error occurred."}``
    """
    import platform

    logger.debug("API: Requesting system and app info.")
    try:
        splash_txt = app_context.splash_txt
        data = {
            "os_type": platform.system(),
            "app_version": config_const.get_installed_version(),
            "splash_text": splash_txt,
        }
        logger.info(f"API: Successfully retrieved system info: {data}")
        return {"status": "success", **data}
    except Exception as e:
        logger.error(f"API: Unexpected error getting system info: {e}", exc_info=True)
        return {"status": "error", "message": "An unexpected error occurred."}


@trigger_plugin_event(
    before="before_server_statuses_updated", after="after_server_statuses_updated"
)
def update_server_statuses(app_context: AppContext) -> Dict[str, Any]:
    from ..utils import server as server_utils

    """Reconciles the status in config files with the runtime state for all servers.

    This function calls the core function to get servers data.
    During that call, for each discovered server, its
    :meth:`~.core.bedrock_server.BedrockServer.get_status` method is invoked.
    This method determines the actual running state of the server process and
    updates the ``status`` field in the server's JSON configuration file
    (e.g., ``<server_name>_config.json``) if there's a discrepancy between
    the stored status and the live status.

    Returns:
        Dict[str, Any]: A dictionary summarizing the operation.
        On success (even with individual server errors during discovery):
        ``{"status": "success", "message": "Status check completed for <n> servers."}`` or
        ``{"status": "error", "message": "Completed with errors: <details>", "updated_servers_count": <n>}``
        (The "error" status here primarily reflects issues during the overall scan,
        like directory access problems, rather than individual server status update failures,
        which are logged and included in the message if `discovery_errors` occur.)
    """
    updated_servers_count = 0
    error_messages = []
    logger.debug("API: Updating all server statuses...")

    try:
        # get_servers_data() now handles the reconciliation internally.
        # It returns both the server data and any errors encountered during discovery.
        all_servers_data, discovery_errors = server_utils.get_servers_data(
            app_context=app_context
        )
        if discovery_errors:
            error_messages.extend(discovery_errors)

        for server_data in all_servers_data:
            server_name = server_data.get("name")
            if not server_name:
                continue

            try:
                # The status is already reconciled by the get_servers_data call.
                logger.info(
                    f"API: Status for '{server_name}' was reconciled by get_servers_data."
                )
                updated_servers_count += 1
            except Exception as e:
                # This block catches errors if processing a specific server's data fails post-discovery.
                msg = f"Could not update status for server '{server_name}': {e}"
                logger.error(f"API.update_server_statuses: {msg}", exc_info=True)
                error_messages.append(msg)

        if error_messages:
            return {
                "status": "error",
                "message": f"Completed with errors: {'; '.join(error_messages)}",
                "updated_servers_count": updated_servers_count,
            }
        return {
            "status": "success",
            "message": f"Status check completed for {updated_servers_count} servers.",
        }

    except BSMError as e:
        logger.error(f"API: Setup error during status update: {e}", exc_info=True)
        return {"status": "error", "message": f"Error accessing directories: {e}"}
    except Exception as e:
        logger.error(f"API: Unexpected error during status update: {e}", exc_info=True)
        return {"status": "error", "message": f"An unexpected error occurred: {e}"}
