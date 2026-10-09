"""Filesystem permission and removal operations for Bedrock servers."""

import logging
import os
from typing import TYPE_CHECKING

import aiofiles
import aiofiles.ospath

from ...error import (
    AppFileNotFoundError,
    FileOperationError,
    MissingArgumentError,
    PermissionsError,
)
from ...logging import log_operation_error
from ..system import base as system_base

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from ..bedrock_server import BedrockServer


async def set_filesystem_permissions(server: "BedrockServer") -> None:
    """Sets appropriate filesystem permissions for the server's installation directory asynchronously."""
    if not await server.is_installed():
        raise AppFileNotFoundError(
            server.paths.server_dir,
            "Cannot set permissions: Server installation directory or executable not found",
        )
    logger.debug(
        "Setting filesystem permissions for server directory: %s",
        server.paths.server_dir,
    )
    try:
        await system_base.set_server_folder_permissions(server.paths.server_dir)
        logger.debug(
            "Successfully set permissions for server '%s' at '%s'.",
            server.server_name,
            server.paths.server_dir,
        )
    except (MissingArgumentError, AppFileNotFoundError, PermissionsError) as e_perm:
        log_operation_error(
            logger,
            "Failed to set permissions for '%s': %s",
            server.paths.server_dir,
            e_perm,
            error=e_perm,
        )
        raise
    except Exception as e_unexp:
        log_operation_error(
            logger,
            "Unexpected error setting permissions for '%s': %s",
            server.server_name,
            e_unexp,
            error=e_unexp,
        )
        raise PermissionsError(
            f"Unexpected error setting permissions for server '{server.server_name}': {e_unexp}"
        ) from e_unexp


async def delete_server_files(
    server: "BedrockServer",
    item_description_prefix: str = "server installation files for",
) -> bool:
    """Deletes the server's entire installation directory asynchronously."""
    if not await aiofiles.ospath.exists(server.paths.server_dir):
        logger.debug(
            "Server directory '%s' for '%s' does not exist. Nothing to delete.",
            server.paths.server_dir,
            server.server_name,
        )
        return True
    logger.debug(
        "Deleting server '%s' at '%s'.", server.server_name, server.paths.server_dir
    )
    return await system_base.delete_path_robustly(
        server.paths.server_dir, f"{item_description_prefix} '{server.server_name}'"
    )


async def _delete_all_data(server: "BedrockServer") -> None:
    """Remove files first, then discard persisted and runtime state."""
    if await server.is_running():
        await server.stop()
    if await server.is_running():
        raise FileOperationError(
            f"Cannot delete running server '{server.server_name}'."
        )

    paths = [server.paths.server_dir, server.paths.server_config_dir]
    backup_root = server.settings.get("paths.backups")
    if backup_root:
        paths.append(os.path.join(backup_root, server.server_name))
    failures = []
    for path in paths:
        if await aiofiles.ospath.exists(path):
            if not await system_base.delete_path_robustly(
                path, f"data for server '{server.server_name}'"
            ):
                failures.append(path)
    if failures:
        raise FileOperationError(
            f"Failed to delete data for '{server.server_name}': {', '.join(failures)}"
        )

    try:
        if server.storage and server.state:
            await server.storage.delete_server(server.state, server.server_name)
        elif server.storage:
            async with server.storage.transaction() as session:
                await server.storage.server_repo.delete_server(
                    session, server.server_name
                )
        elif server.state:
            server.state.servers.remove(server.server_name)
            server.state.runtime.remove_server_runtime(server.server_name)
    except Exception as error:
        raise FileOperationError(
            f"Failed to delete database entries for '{server.server_name}': {error}"
        ) from error
    logger.info("Deleted all data for server '%s'.", server.server_name)


async def delete_all_data(server: "BedrockServer") -> None:
    """Serialize the operation with other mutations of this server."""
    async with server.operation_lock:
        await _delete_all_data(server)
