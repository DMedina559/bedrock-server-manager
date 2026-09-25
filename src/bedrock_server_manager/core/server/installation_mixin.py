"""Provides the :class:`.ServerInstallationMixin` for the :class:`~.core.bedrock_server.BedrockServer` class.

This mixin is focused on aspects of a server's lifecycle that involve its
presence and integrity on the filesystem, as well as its complete removal.
Key responsibilities include:

    - Validating if a server installation appears correct (e.g., server directory
      and executable exist).
    - Setting appropriate filesystem permissions for the server's installation
      directory, delegating to :func:`~.core.system.base.set_server_folder_permissions`.
    - Providing methods for deleting server-specific data:
        - :meth:`.ServerInstallationMixin.delete_server_files`: Deletes the main
          server installation directory.
        - :meth:`.ServerInstallationMixin.delete_all_data`: A comprehensive and
          **DESTRUCTIVE** operation that removes the installation directory,
          JSON configuration, all backups for the server, and attempts to
          remove associated systemd services on Linux.

**Warning**: Methods within this mixin, particularly `delete_all_data`, can
lead to irreversible data loss if not used carefully.
"""

import os
from typing import Any

import aiofiles
import aiofiles.os
import aiofiles.ospath
from sqlalchemy import delete

from ...error import (
    AppFileNotFoundError,
    FileOperationError,
    MissingArgumentError,
    PermissionsError,
)
from ..system import base as system_base
from .base_server_mixin import BedrockServerBaseMixin


class ServerInstallationMixin(BedrockServerBaseMixin):
    """Provides methods for validating, managing filesystem permissions, and deleting server installations."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    async def validate_installation(self) -> bool:
        """Validates that the server installation directory and executable exist asynchronously."""
        self.logger.debug(
            f"Validating installation for server '{self.server_name}' in directory: {self.server_dir} asynchronously"
        )

        if not await aiofiles.ospath.isdir(self.server_dir):
            raise AppFileNotFoundError(self.server_dir, "Server directory")

        if not await aiofiles.ospath.isfile(self.bedrock_executable_path):
            raise AppFileNotFoundError(
                self.bedrock_executable_path, "Server executable"
            )

        self.logger.debug(
            f"Server '{self.server_name}' installation validation successful."
        )
        return True

    async def is_installed(self) -> bool:
        """Checks if the server installation is valid asynchronously, without raising exceptions."""
        try:
            return await self.validate_installation()
        except AppFileNotFoundError:
            self.logger.debug(
                f"is_installed check: Server '{self.server_name}' not found or installation invalid (directory or executable missing)."
            )
            return False

    async def set_filesystem_permissions(self) -> None:
        """Sets appropriate filesystem permissions for the server's installation directory asynchronously."""
        if not await self.is_installed():
            raise AppFileNotFoundError(
                self.server_dir,
                "Cannot set permissions: Server installation directory or executable not found",
            )

        self.logger.info(
            f"Setting filesystem permissions for server directory: {self.server_dir} asynchronously"
        )
        try:
            await system_base.set_server_folder_permissions(self.server_dir)
            self.logger.info(
                f"Successfully set permissions for server '{self.server_name}' at '{self.server_dir}'."
            )
        except (
            MissingArgumentError,
            AppFileNotFoundError,
            PermissionsError,
        ) as e_perm:
            self.logger.error(
                f"Failed to set permissions for '{self.server_dir}': {e_perm}"
            )
            raise
        except Exception as e_unexp:
            self.logger.error(
                f"Unexpected error setting permissions for '{self.server_name}': {e_unexp}",
                exc_info=True,
            )
            raise PermissionsError(
                f"Unexpected error setting permissions for server '{self.server_name}': {e_unexp}"
            ) from e_unexp

    async def delete_server_files(
        self, item_description_prefix: str = "server installation files for"
    ) -> bool:
        """Deletes the server's entire installation directory asynchronously."""
        if not await aiofiles.ospath.exists(self.server_dir):
            self.logger.info(
                f"Server directory '{self.server_dir}' for '{self.server_name}' does not exist. Nothing to delete."
            )
            return True

        self.logger.warning(
            f"Attempting to delete {item_description_prefix} server '{self.server_name}' at '{self.server_dir}' asynchronously. THIS IS DESTRUCTIVE."
        )

        return await system_base.delete_path_robustly(
            self.server_dir,
            f"{item_description_prefix} '{self.server_name}'",
        )

    async def delete_all_data(self) -> None:
        """Deletes **ALL** data associated with this Bedrock server instance asynchronously."""
        server_install_dir = self.server_dir
        server_json_config_subdir = self.server_config_dir

        backup_base_dir = self.settings.get("paths.backups")
        server_backup_dir_path = (
            os.path.join(backup_base_dir, self.server_name) if backup_base_dir else None
        )

        self.logger.warning(
            f"!!! DESTRUCTIVE ACTION: Preparing to delete ALL data for server '{self.server_name}' asynchronously !!!"
        )
        self.logger.info(f"  - Target installation directory: {server_install_dir}")
        if server_backup_dir_path:
            self.logger.info(f"  - Target backup directory: {server_backup_dir_path}")
        else:
            self.logger.info("  - No backup directory path configured or found.")

        paths_to_check_existence = [server_install_dir]
        if server_backup_dir_path:
            paths_to_check_existence.append(server_backup_dir_path)

        any_primary_data_exists = False
        for p in paths_to_check_existence:
            if p and await aiofiles.ospath.exists(p):
                any_primary_data_exists = True
                break

        if not any_primary_data_exists:
            self.logger.info(
                f"Server '{self.server_name}': Neither installation nor backup directories exist. Skipping deletion."
            )
            return

        is_running: bool = False
        try:
            is_running = await getattr(self, "is_running")()
        except AttributeError:
            self.logger.warning(
                f"[{self.server_name}] 'is_running' not found. Assuming stopped."
            )
        if is_running:
            self.logger.info(
                f"Server '{self.server_name}' is currently running. Stopping before deletion..."
            )
            try:
                await getattr(self, "stop")()
            except AttributeError:
                self.logger.warning(
                    f"[{self.server_name}] 'stop' not found. Cannot stop before deletion."
                )

        failed_deletions = []

        if await aiofiles.ospath.exists(server_install_dir):
            if not await self.delete_server_files("installation files for"):
                failed_deletions.append(server_install_dir)

        if await aiofiles.ospath.exists(server_json_config_subdir):
            success = await system_base.delete_path_robustly(
                server_json_config_subdir,
                f"JSON config directory for server '{self.server_name}'",
            )
            if not success:
                failed_deletions.append(server_json_config_subdir)

        if server_backup_dir_path and await aiofiles.ospath.exists(
            server_backup_dir_path
        ):
            success = await system_base.delete_path_robustly(
                server_backup_dir_path,
                f"backup directory for server '{self.server_name}'",
            )
            if not success:
                failed_deletions.append(server_backup_dir_path)

        pid_file_path = getattr(self, "bedrock_pid_file_path", None)
        if pid_file_path and await aiofiles.ospath.exists(pid_file_path):
            try:
                await aiofiles.os.remove(pid_file_path)
                self.logger.info(
                    f"Successfully deleted PID file for server '{self.server_name}': {pid_file_path}"
                )
            except OSError as e:
                self.logger.error(
                    f"Failed to delete PID file '{pid_file_path}' for server '{self.server_name}': {e}"
                )
                failed_deletions.append(pid_file_path)

        if getattr(self.app_context, "_storage", None) is not None:
            try:
                from ...db.models import ServerBan

                async with self.app_context.storage.transaction() as session:
                    db_server = (
                        await self.app_context.storage.server_repo.get_server_by_name(
                            session, self.server_name
                        )
                    )
                    if db_server:
                        await session.execute(
                            delete(ServerBan).filter(
                                ServerBan.server_id == db_server.id
                            )
                        )
                        await session.delete(db_server)

                if self.server_name in self.app_context.state.servers.servers:
                    del self.app_context.state.servers.servers[self.server_name]

                self.logger.info(
                    f"Successfully deleted server '{self.server_name}' and its associated data from the database."
                )
            except Exception as e:
                self.logger.error(
                    f"Failed to remove database entries for server '{self.server_name}': {e}"
                )
                failed_deletions.append("Database Entries")

        if failed_deletions:
            error_msg = f"Failed to delete ALL data for '{self.server_name}'. The following paths/items could not be removed: {', '.join(failed_deletions)}"
            self.logger.error(error_msg)
            raise FileOperationError(error_msg)

        self.logger.info(
            f"Successfully deleted ALL data for server '{self.server_name}' asynchronously."
        )
