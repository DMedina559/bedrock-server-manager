# bedrock_server_manager/api/utils.py
"""Provides utility functions and a context manager for the API layer.

This module offers a collection of helper functions that support other API
modules or perform general application-wide tasks. Key functionalities include:

- Server validation:
    - :func:`~.validate_server_exist`: Checks if a server is correctly installed.
    - :func:`~.validate_server_name_format`: Validates the naming convention for servers.
- Server status management:
    - :func:`~.update_server_statuses`: Reconciles the configured status of all
      servers with their actual runtime state.
- System interaction:
    - :func:`~.get_system_and_app_info`: Retrieves basic OS and application version details.
- Lifecycle management:
    - :func:`~.server_lifecycle_manager`: A context manager for safely performing
      operations that require a server to be temporarily stopped and then restarted.

These utilities are designed to be used by other API modules or higher-level
application logic to encapsulate common or complex operations.
"""
import logging
from typing import Dict, Any, Optional
from contextlib import contextmanager

# Plugin system imports to bridge API functionality.
from ..plugins import plugin_method
from ..plugins.event_trigger import trigger_plugin_event

# Local application imports.
from ..core import utils as core_utils
from .server import (
    start_server as api_start_server,
    stop_server as api_stop_server,
)
from ..error import (
    BSMError,
    UserInputError,
    ServerStartError,
)
from ..context import AppContext

logger = logging.getLogger(__name__)


@plugin_method("validate_server_exist")
def validate_server_exist(server_name: str, app_context: AppContext) -> Dict[str, Any]:
    """Validates if a server is correctly installed.

    This function checks for the existence of the server's directory and its
    executable by instantiating a :class:`~.core.bedrock_server.BedrockServer`
    object for the given `server_name` and then calling its
    :meth:`~.core.server.installation_mixin.ServerInstallationMixin.is_installed` method.

    Args:
        server_name (str): The name of the server to validate.

    Returns:
        Dict[str, Any]: A dictionary with the operation status.
        If valid: ``{"status": "success", "message": "Server '<server_name>' exists and is valid."}``
        If not installed/invalid: ``{"status": "error", "message": "Server '<server_name>' is not installed..."}``
        If config error: ``{"status": "error", "message": "Configuration error: <details>"}``

    Raises:
        BSMError: Can be raised by :class:`~.core.bedrock_server.BedrockServer`
            during instantiation if core application settings are misconfigured.
    """
    if not server_name:
        return {"status": "error", "message": "Server name cannot be empty."}

    logger.debug(f"API: Validating existence of server '{server_name}'...")
    try:
        # Instantiating BedrockServer also validates underlying configurations.
        server = app_context.get_server(server_name)

        # is_installed() returns a simple boolean.
        if server.is_installed():
            logger.debug(f"API: Server '{server_name}' validation successful.")
            return {
                "status": "success",
                "message": f"Server '{server_name}' exists and is valid.",
            }
        else:
            logger.debug(
                f"API: Validation failed for '{server_name}'. It is not correctly installed."
            )
            return {
                "status": "error",
                "message": f"Server '{server_name}' is not installed or the installation is invalid.",
            }

    except BSMError as e:  # Catches config issues from BedrockServer instantiation.
        logger.error(
            f"API: Configuration error during validation for '{server_name}': {e}",
            exc_info=True,
        )
        return {"status": "error", "message": f"Configuration error: {e}"}
    except Exception as e:
        logger.error(
            f"API: Unexpected error validating server '{server_name}': {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"An unexpected validation error occurred: {e}",
        }


@plugin_method("validate_server_name_format")
def validate_server_name_format(server_name: str) -> Dict[str, str]:
    """Validates the format of a potential server name.

    This is a stateless check (does not verify if the server actually exists)
    that delegates to
    :func:`~bedrock_server_manager.core.utils.core_validate_server_name_format`.
    It ensures new server names conform to allowed character sets (alphanumeric,
    hyphens, underscores) and are not empty.

    Args:
        server_name (str): The server name string to validate.

    Returns:
        Dict[str, str]: A dictionary with the operation status.
        If format is valid: ``{"status": "success", "message": "Server name format is valid."}``
        If format is invalid: ``{"status": "error", "message": "<validation_error_detail>"}``
    """
    logger.debug(f"API: Validating format for '{server_name}'")
    try:
        # Delegate validation to the core utility function.
        core_utils.core_validate_server_name_format(server_name)
        logger.debug(f"API: Format valid for '{server_name}'.")
        return {"status": "success", "message": "Server name format is valid."}
    except UserInputError as e:
        logger.debug(f"API: Invalid format for '{server_name}': {e}")
        return {"status": "error", "message": str(e)}
    except Exception as e:
        logger.error(f"API: Unexpected error for '{server_name}': {e}", exc_info=True)
        return {"status": "error", "message": f"An unexpected error occurred: {e}"}


@trigger_plugin_event(after="after_server_statuses_updated")
def update_server_statuses(app_context: AppContext) -> Dict[str, Any]:
    """Reconciles the status in config files with the runtime state for all servers.

    This function calls
    :meth:`~bedrock_server_manager.core.manager.BedrockServerManager.get_servers_data`.
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
        manager = app_context.manager
        # get_servers_data() from the manager now handles the reconciliation internally.
        # It returns both the server data and any errors encountered during discovery.
        all_servers_data, discovery_errors = manager.get_servers_data(
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


@plugin_method("get_system_and_app_info")
def get_system_and_app_info(app_context: AppContext) -> Dict[str, Any]:
    """Retrieves basic system and application information.

    Uses :class:`~.core.manager.BedrockServerManager` to get OS type and app version.

    Returns:
        Dict[str, Any]: On success: ``{"status": "success", "data": {"os_type": "...", "app_version": "..."}}``.
        On error: ``{"status": "error", "message": "An unexpected error occurred."}``
    """
    logger.debug("API: Requesting system and app info.")
    try:
        manager = app_context.manager
        data = {
            "os_type": manager.get_os_type(),
            "app_version": manager.get_app_version(),
        }
        logger.info(f"API: Successfully retrieved system info: {data}")
        return {"status": "success", "data": data}
    except Exception as e:
        logger.error(f"API: Unexpected error getting system info: {e}", exc_info=True)
        return {"status": "error", "message": "An unexpected error occurred."}


def stop_all_servers(app_context: AppContext):
    """Stops all running servers."""
    logger.info("API: Stopping all servers...")
    manager = app_context.manager
    result = manager.get_servers_data(app_context=app_context)
    if isinstance(result, tuple) and len(result) == 2:
        servers_data, _ = result
    else:
        servers_data = []

    for server_data in servers_data:
        server_name = server_data.get("name")
        server = app_context.get_server(server_name)
        if server.is_running():
            api_stop_server(server_name, app_context=app_context)


@plugin_method("server_lifecycle_manager")
@contextmanager
def server_lifecycle_manager(
    server_name: str,
    stop_before: bool,
    app_context: AppContext,
    start_after: bool = True,
    restart_on_success_only: bool = False,
):
    """A context manager to safely stop and restart a server for an operation.

    This manager, when ``stop_before=True``, will attempt to stop a server using
    :func:`~.api_stop_server` if it is running. It then yields control to the
    wrapped code block. In its ``finally`` clause, it handles restarting the
    server (if ``start_after=True`` and it was originally running) using
    :func:`~.api_start_server` with ``mode="detached"``. This ensures an attempt
    to return the server to its original state even if the operation within
    the ``with`` block fails.

    Args:
        server_name (str): The name of the server to manage.
        stop_before (bool): If ``True``, the server will be stopped if it's running
            before the ``with`` block is entered. If stopping fails, the context
            manager may not yield control.
        start_after (bool, optional): If ``True``, the server will be restarted after
            the ``with`` block if it was running initially. Defaults to ``True``.
        restart_on_success_only (bool, optional): If ``True``, the server will only
            be restarted if the ``with`` block completes without raising an
            exception. Defaults to ``False``.

    Yields:
        None.

    Raises:
        ServerStopError: If ``stop_before=True`` and the initial attempt to stop
            the server fails critically (though the current implementation returns a dict).
        ServerStartError: If ``start_after=True`` and the server fails to restart
            after the operation. This is raised if the original operation in the
            ``with`` block succeeded but the subsequent restart failed.
        Exception: Re-raises any exception that occurs within the ``with`` block itself.
        BSMError: For other application-specific errors during server interactions.
    """
    server = app_context.get_server(server_name)
    was_running = False
    operation_succeeded = True

    # If the operation doesn't require a server stop, just yield and exit.
    if not stop_before:
        logger.debug(
            f"Context Mgr: Stop/Start not flagged for '{server_name}'. Skipping."
        )
        yield
        return

    try:
        # --- PRE-OPERATION: STOP SERVER ---
        if server.is_running():
            was_running = True
            logger.info(f"Context Mgr: Server '{server_name}' is running. Stopping...")
            stop_result = api_stop_server(server_name, app_context=app_context)
            if stop_result.get("status") == "error":
                error_msg = f"Failed to stop server '{server_name}': {stop_result.get('message')}. Aborted."
                logger.error(error_msg)
                # Do not proceed if the server can't be stopped.
                return {"status": "error", "message": error_msg}
            logger.info(f"Context Mgr: Server '{server_name}' stopped.")
        else:
            logger.debug(
                f"Context Mgr: Server '{server_name}' is not running. No stop needed."
            )

        # Yield control to the wrapped code block.
        yield

    except Exception:
        # If an error occurs in the `with` block, record it and re-raise.
        operation_succeeded = False
        logger.error(
            f"Context Mgr: Exception occurred during managed operation for '{server_name}'.",
            exc_info=True,
        )
        raise
    finally:
        # --- POST-OPERATION: RESTART SERVER ---
        # Only restart if the server was running initially and `start_after` is true.
        if was_running and start_after:
            should_restart = True
            # If `restart_on_success_only` is set, check if the operation failed.
            if restart_on_success_only and not operation_succeeded:
                should_restart = False
                logger.warning(
                    f"Context Mgr: Operation for '{server_name}' failed. Skipping restart as requested."
                )

            if should_restart:
                logger.info(f"Context Mgr: Restarting server '{server_name}'...")
                try:
                    # Use the API function to ensure detached mode and proper handling.
                    start_result = api_start_server(
                        server_name, app_context=app_context
                    )
                    if start_result.get("status") == "error":
                        raise ServerStartError(
                            f"Failed to restart '{server_name}': {start_result.get('message')}"
                        )
                    logger.info(
                        f"Context Mgr: Server '{server_name}' restart initiated."
                    )
                except BSMError as e:
                    logger.error(
                        f"Context Mgr: FAILED to restart '{server_name}': {e}",
                        exc_info=True,
                    )
                    # If the original operation succeeded, the failure to restart
                    # becomes the primary error to report.
                    if operation_succeeded:
                        raise
