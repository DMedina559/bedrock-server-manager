import asyncio
import logging
import os
from typing import Optional

from ..context import AppContext
from ..error import (
    BSMError,
    FileOperationError,
    InvalidServerNameError,
    MissingArgumentError,
)
from ..logging import log_operation_error
from ..plugins.api_bridge import api_method
from ..plugins.api_contract import validate_contract
from ..plugins.event_trigger import trigger_event
from ..plugins.runtime_capabilities import server_lifecycle_manager
from ..utils import get_timestamp
from .models.world import (
    ExportWorldRequest,
    ExportWorldResponse,
    GetWorldNameRequest,
    GetWorldNameResponse,
    ImportWorldRequest,
    ImportWorldResponse,
    ResetWorldRequest,
    ResetWorldResponse,
)

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
thread-safe using a per-server operation lock (``server.operation_lock``) to prevent data corruption.
For actions that require the server to be offline (like import or reset),
this module utilizes the
:func:`~bedrock_server_manager.api.server.server_lifecycle_manager`
to safely stop and restart the server. All functions are exposed to the
plugin system.
"""


logger = logging.getLogger(__name__)


@api_method("get_world_name")
async def get_world_name(
    request: GetWorldNameRequest, *, app_context: AppContext
) -> GetWorldNameResponse:
    """Retrieves the configured world name (`level-name`) for a server.

    Accepts GetWorldNameRequest and returns GetWorldNameResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    server_name = request.server_name
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    logger.debug("Attempting to get world name for server '%s'...", server_name)
    try:
        server = app_context.get_server(server_name)
        world_name_str = await server.get_world_name()
        logger.debug("Retrieved world name for '%s': '%s'", server_name, world_name_str)
        return GetWorldNameResponse.model_validate(
            {"status": "success", "world_name": world_name_str}
        )
    except BSMError as e:
        log_operation_error(
            logger, "Failed to get world name for '%s': %s", server_name, e, error=e
        )
        raise
    except Exception as e:
        log_operation_error(
            logger,
            "Unexpected error getting world name for '%s': %s",
            server_name,
            e,
            error=e,
        )
        raise


@api_method("export_world")
@trigger_event(
    before="before_world_export",
    after="after_world_export",
    identity_keys=("server_name", "export_dir"),
)
async def export_world(
    request: ExportWorldRequest, *, app_context: AppContext
) -> ExportWorldResponse:
    """Exports the server's currently active world to a .mcworld archive.

    Accepts ExportWorldRequest and returns ExportWorldResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    server_name = request.server_name
    export_dir = request.export_dir
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    server = app_context.get_server(server_name)
    try:
        await server.operation_lock.acquire(timeout=300)
    except asyncio.TimeoutError:
        logger.warning(
            "An operation for '%s' is already in progress. Skipping concurrent export.",
            server_name,
        )
        return ExportWorldResponse.model_validate(
            {
                "status": "skipped",
                "message": "A world operation is already in progress.",
            }
        )
    try:
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
        logger.debug("Initiating world export for '%s'", server_name)
        try:
            os.makedirs(effective_export_dir, exist_ok=True)
            world_name_str = await server.get_world_name()
            timestamp = get_timestamp()
            export_filename = f"{world_name_str}_export_{timestamp}.mcworld"
            export_file_path = os.path.join(effective_export_dir, export_filename)
            logger.debug(
                "Exporting world '%s' to '%s'...", world_name_str, export_file_path
            )
            await server.worlds.export_world(world_name_str, export_file_path)
            logger.debug(
                "World for server '%s' exported to '%s'.", server_name, export_file_path
            )
            return ExportWorldResponse.model_validate(
                {
                    "status": "success",
                    "export_file": export_file_path,
                    "message": f"World '{world_name_str}' exported successfully to {export_filename}.",
                }
            )
        except (BSMError, ValueError) as e:
            log_operation_error(
                logger, "Failed to export world for '%s': %s", server_name, e, error=e
            )
            raise
        except Exception as e:
            log_operation_error(
                logger,
                "Unexpected error exporting world for '%s': %s",
                server_name,
                e,
                error=e,
            )
            raise
    finally:
        server.operation_lock.release()


@api_method("import_world")
@trigger_event(
    before="before_world_import",
    after="after_world_import",
    identity_keys=("server_name", "selected_file_path"),
)
async def import_world(
    request: ImportWorldRequest, *, app_context: AppContext
) -> ImportWorldResponse:
    """Imports a world from a .mcworld file, replacing the active world.

    Accepts ImportWorldRequest and returns ImportWorldResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    server_name = request.server_name
    selected_file_path = request.selected_file_path
    stop_start_server = request.stop_start_server
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    if not selected_file_path:
        raise MissingArgumentError(".mcworld file path cannot be empty.")
    server = app_context.get_server(server_name)
    try:
        await server.operation_lock.acquire(timeout=300)
    except asyncio.TimeoutError:
        logger.debug(
            "An operation for '%s' is already in progress. Skipping concurrent import.",
            server_name,
        )
        return ImportWorldResponse.model_validate(
            {
                "status": "skipped",
                "message": "A world operation is already in progress.",
            }
        )
    try:
        selected_filename = os.path.basename(selected_file_path)
        logger.debug(
            "Initiating world import for '%s' from '%s' (Stop/Start: %s)",
            server_name,
            selected_filename,
            stop_start_server,
        )
        try:
            if not os.path.isfile(selected_file_path):
                raise FileNotFoundError(
                    f"Source .mcworld file not found: {selected_file_path}"
                )
            imported_world_name: Optional[str] = None
            async with server_lifecycle_manager(
                server_name, stop_before=stop_start_server, app_context=app_context
            ):
                logger.debug(
                    "Importing world from '%s' into server '%s'...",
                    selected_filename,
                    server_name,
                )
                imported_world_name = await server.worlds.import_world(
                    selected_file_path
                )
            logger.debug(
                "World import from '%s' for server '%s' completed.",
                selected_filename,
                server_name,
            )
            return ImportWorldResponse.model_validate(
                {
                    "status": "success",
                    "message": f"World '{imported_world_name or 'Unknown'}' imported successfully from {selected_filename}.",
                }
            )
        except (BSMError, FileNotFoundError) as e:
            log_operation_error(
                logger, "Failed to import world for '%s': %s", server_name, e, error=e
            )
            raise
        except Exception as e:
            log_operation_error(
                logger,
                "Unexpected error importing world for '%s': %s",
                server_name,
                e,
                error=e,
            )
            raise
    finally:
        server.operation_lock.release()


@validate_contract
@trigger_event(
    before="before_world_reset",
    after="after_world_reset",
    identity_keys=("server_name",),
)
async def reset_world(
    request: ResetWorldRequest, *, app_context: AppContext
) -> ResetWorldResponse:
    """Resets the server's world by deleting the active world directory.

    Accepts ResetWorldRequest and returns ResetWorldResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    server_name = request.server_name
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty for API request.")
    server = app_context.get_server(server_name)
    try:
        await server.operation_lock.acquire(timeout=300)
    except asyncio.TimeoutError:
        logger.debug(
            "An operation for '%s' is already in progress. Skipping concurrent reset.",
            server_name,
        )
        return ResetWorldResponse.model_validate(
            {
                "status": "skipped",
                "message": "A world operation is already in progress.",
            }
        )
    try:
        logger.debug("Initiating world reset for server '%s'...", server_name)
        try:
            world_name_for_msg = await server.get_world_name()
            async with server_lifecycle_manager(
                server_name,
                stop_before=True,
                start_after=True,
                restart_on_success_only=True,
                app_context=app_context,
            ):
                logger.debug(
                    "Attempting to delete world directory for world '%s'...",
                    world_name_for_msg,
                )
                await server.worlds.delete_world()
            logger.debug(
                "World '%s' for server '%s' has been successfully reset.",
                world_name_for_msg,
                server_name,
            )
            return ResetWorldResponse.model_validate(
                {
                    "status": "success",
                    "message": f"World '{world_name_for_msg}' reset successfully.",
                }
            )
        except BSMError as e:
            log_operation_error(
                logger, "Failed to reset world for '%s': %s", server_name, e, error=e
            )
            raise
        except Exception as e:
            log_operation_error(
                logger,
                "Unexpected error resetting world for '%s': %s",
                server_name,
                e,
                error=e,
            )
            raise
    finally:
        server.operation_lock.release()
