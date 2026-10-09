"""Filesystem permission and removal operations for Bedrock servers."""

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
from ..system import base as system_base

if TYPE_CHECKING:
    from ..bedrock_server import BedrockServer


async def set_filesystem_permissions(server: "BedrockServer") -> None:
    """Sets appropriate filesystem permissions for the server's installation directory asynchronously."""
    if not await server.is_installed():
        raise AppFileNotFoundError(
            server.server_dir,
            "Cannot set permissions: Server installation directory or executable not found",
        )
    server.logger.info(
        f"Setting filesystem permissions for server directory: {server.server_dir} asynchronously"
    )
    try:
        await system_base.set_server_folder_permissions(server.server_dir)
        server.logger.info(
            f"Successfully set permissions for server '{server.server_name}' at '{server.server_dir}'."
        )
    except (MissingArgumentError, AppFileNotFoundError, PermissionsError) as e_perm:
        server.logger.error(
            f"Failed to set permissions for '{server.server_dir}': {e_perm}"
        )
        raise
    except Exception as e_unexp:
        server.logger.error(
            f"Unexpected error setting permissions for '{server.server_name}': {e_unexp}",
            exc_info=True,
        )
        raise PermissionsError(
            f"Unexpected error setting permissions for server '{server.server_name}': {e_unexp}"
        ) from e_unexp


async def delete_server_files(
    server: "BedrockServer",
    item_description_prefix: str = "server installation files for",
) -> bool:
    """Deletes the server's entire installation directory asynchronously."""
    if not await aiofiles.ospath.exists(server.server_dir):
        server.logger.info(
            f"Server directory '{server.server_dir}' for '{server.server_name}' does not exist. Nothing to delete."
        )
        return True
    server.logger.warning(
        f"Attempting to delete {item_description_prefix} server '{server.server_name}' at '{server.server_dir}' asynchronously. THIS IS DESTRUCTIVE."
    )
    return await system_base.delete_path_robustly(
        server.server_dir, f"{item_description_prefix} '{server.server_name}'"
    )


async def _delete_all_data(server: "BedrockServer") -> None:
    """Remove files first, then discard persisted and runtime state."""
    if await server.is_running():
        await server.stop()
    if await server.is_running():
        raise FileOperationError(
            f"Cannot delete running server '{server.server_name}'."
        )

    paths = [server.server_dir, server.server_config_dir]
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
    server.logger.info("Deleted all data for server '%s'.", server.server_name)


async def delete_all_data(server: "BedrockServer") -> None:
    """Serialize the operation with other mutations of this server."""
    async with server.operation_lock:
        await _delete_all_data(server)
