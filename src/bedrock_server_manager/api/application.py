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
import os
from typing import Any, Dict, List

from ..context import AppContext
from ..core import utils as core_utils
from ..core.system import find_files
from ..error import AppFileNotFoundError, BSMError, FileError, FileOperationError
from ..plugins import plugin_method

logger = logging.getLogger(__name__)


def _list_content_files(
    content_dir: str | None, sub_folder: str, extensions: List[str]
) -> List[str]:
    """
    Internal helper to list files with specified extensions from a sub-folder
    within the global content directory.
    """
    if not content_dir or not os.path.isdir(content_dir):
        raise AppFileNotFoundError(str(content_dir), "Content directory")

    target_dir = os.path.join(content_dir, sub_folder)
    if not os.path.isdir(target_dir):
        logger.debug(
            f"BSM: Content sub-directory '{target_dir}' not found. Returning empty list."
        )
        return []

    found_files: List[str] = []
    try:
        for ext in extensions:
            pattern = f"*{ext}" if ext.startswith(".") else f"*.{ext}"
            files = find_files(target_dir, pattern=pattern)
            found_files.extend(os.path.abspath(str(f)) for f in files)
    except OSError as e:
        raise FileOperationError(
            f"Error scanning content directory {target_dir}: {e}"
        ) from e
    return sorted(list(set(found_files)))


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
        worlds = _list_content_files(content_dir, "worlds", [".mcworld"])
        return {"status": "success", "files": worlds}
    except FileError as e:
        # Handle specific file-related errors.
        return {"status": "error", "message": str(e)}
    except Exception as e:
        logger.error(f"API: Unexpected error listing worlds: {e}", exc_info=True)
        return {"status": "error", "message": f"Unexpected error: {str(e)}"}


@plugin_method("list_available_addons_api")
def list_available_addons_api(app_context: AppContext) -> Dict[str, Any]:
    """Lists available .mcaddon and .mcpack files from the content directory.

    Scans the ``addons`` sub-folder within the application's global content directory.

    Returns:
        Dict[str, Any]: A dictionary with the operation result.
        On success: ``{"status": "success", "files": List[str]}`` where `files` is a
        list of absolute paths to ``.mcaddon`` or ``.mcpack`` files.
        On error: ``{"status": "error", "message": "<error_message>"}``.

    Raises:
        FileError: If the content directory is not configured or accessible.
    """
    logger.debug("API: Requesting list of available addons.")
    try:
        content_dir = app_context.settings.get("paths.content")
        addons = _list_content_files(content_dir, "addons", [".mcpack", ".mcaddon"])
        return {"status": "success", "files": addons}
    except FileError as e:
        # Handle specific file-related errors.
        return {"status": "error", "message": str(e)}
    except Exception as e:
        logger.error(f"API: Unexpected error listing addons: {e}", exc_info=True)
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

    try:
        # Call the core function which returns both data and potential errors.
        servers_data, bsm_error_messages = core_utils.get_servers_data(
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
