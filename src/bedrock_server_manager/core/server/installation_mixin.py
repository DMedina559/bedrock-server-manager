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
from sqlalchemy import delete, select

from ...error import (
    AppFileNotFoundError,
    FileOperationError,
    MissingArgumentError,
    PermissionsError,
)
from ..system import base as system_base
from .base_server_mixin import BedrockServerBaseMixin


class ServerInstallationMixin(BedrockServerBaseMixin):
    """Provides methods for validating, managing filesystem permissions, and deleting server installations.

    This mixin extends :class:`.BedrockServerBaseMixin` and focuses on the
    physical presence and state of the server's files on the disk, as well as
    the complete removal of all server-related data.

    Key methods include:

        - :meth:`.validate_installation`: Checks if the server directory and executable exist.
        - :meth:`.is_installed`: A non-raising check for installation validity.
        - :meth:`.set_filesystem_permissions`: Applies appropriate permissions to server files.
        - :meth:`.delete_server_files`: Deletes the main server installation directory.
        - :meth:`.delete_all_data`: **DESTRUCTIVE** - Removes all data for the server,
          including installation, configuration, backups, and systemd services (Linux).

    It relies on attributes from :class:`.BedrockServerBaseMixin` (like `server_dir`,
    `bedrock_executable_path`, `logger`) and may depend on methods from other mixins
    (e.g., :meth:`~.ServerProcessMixin.is_running`, :meth:`~.ServerProcessMixin.stop`)
    for operations like stopping a server before deletion.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initializes the ServerInstallationMixin.

        Calls ``super().__init__(*args, **kwargs)`` to participate in cooperative
        multiple inheritance. It depends on attributes initialized by
        :class:`.BedrockServerBaseMixin` and assumes methods from other mixins
        (like :meth:`~.ServerProcessMixin.is_running` and :meth:`~.ServerProcessMixin.stop`)
        will be available on the final composed :class:`~.core.bedrock_server.BedrockServer` object.

        Args:
            *args (Any): Variable length argument list passed to `super()`.
            **kwargs (Any): Arbitrary keyword arguments passed to `super()`.
        """
        super().__init__(*args, **kwargs)
        # Attributes from BedrockServerBaseMixin are available.
        # Methods from other mixins (e.g., ProcessMixin for stop/is_running)
        # are expected on the final composed BedrockServer object.

    async def validate_installation(self) -> bool:
        """Validates that the server installation directory and executable exist asynchronously.

        This method checks for the presence of:

            1. The server's main installation directory (:attr:`.BedrockServerBaseMixin.server_dir`).
            2. The Bedrock server executable within that directory
               (path from :attr:`.BedrockServerBaseMixin.bedrock_executable_path`).

        Returns:
            bool: ``True`` if both the server directory and executable file exist.

        Raises:
            AppFileNotFoundError: If the server directory or the executable
                file does not exist at their expected locations.
        """
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
        """Checks if the server installation is valid asynchronously, without raising exceptions.

        This is a convenience method that calls :meth:`.validate_installation`
        and catches :class:`~.error.AppFileNotFoundError` if validation fails,
        returning ``False`` in such cases.

        Returns:
            bool: ``True`` if the installation is valid (directory and executable exist),
            ``False`` otherwise.
        """
        try:
            return await self.validate_installation()
        except AppFileNotFoundError:
            self.logger.debug(
                f"is_installed check: Server '{self.server_name}' not found or installation invalid (directory or executable missing)."
            )
            return False

    async def set_filesystem_permissions(self) -> None:
        """Sets appropriate filesystem permissions for the server's installation directory asynchronously.

        This method first validates the server installation using :meth:`.is_installed`.
        If valid, it delegates to the platform-agnostic
        :func:`~.core.system.base.set_server_folder_permissions` utility to
        apply the necessary permissions recursively to :attr:`.BedrockServerBaseMixin.server_dir`.
        This is crucial for proper server operation, especially on Linux.

        Raises:
            AppFileNotFoundError: If the server is not installed (i.e.,
                :meth:`.is_installed` returns ``False``).
            PermissionsError: If setting permissions fails (propagated from
                :func:`~.core.system.base.set_server_folder_permissions`).
            MissingArgumentError: If `server_dir` is somehow invalid (propagated).
        """
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
        """Deletes the server's entire installation directory (:attr:`.BedrockServerBaseMixin.server_dir`) asynchronously.

        .. warning::
            This is a **DESTRUCTIVE** operation. It will permanently remove the
            server's main directory and all its contents.

        It uses the :func:`~.core.system.base.delete_path_robustly` utility,
        which attempts to handle read-only files that might otherwise prevent deletion.

        Args:
            item_description_prefix (str, optional): A prefix for logging messages
                to provide context. Defaults to "server installation files for".

        Returns:
            bool: ``True`` if the deletion was successful or if the directory
            did not exist initially. ``False`` if the deletion failed.
        """
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
        """Deletes **ALL** data associated with this Bedrock server instance asynchronously.

        .. danger::
            This is a **HIGHLY DESTRUCTIVE** operation and is irreversible.

            It removes:

                1. The server's main installation directory (:attr:`.BedrockServerBaseMixin.server_dir`).
                2. The server's JSON configuration subdirectory (:attr:`.BedrockServerBaseMixin.server_config_dir`).
                3. The server's entire backup directory (derived from ``paths.backups`` setting).
                4. The server's PID file.
                5. Database entries related to the server (e.g. Server and ServerBan records).

        The method will attempt to stop a running server before proceeding with deletions.
        If any part of the deletion process fails, it raises a
        :class:`~.error.FileOperationError` with details of the failed items.

        Raises:
            FileOperationError: If deleting one or more essential directories or
                files fails. The error message will summarize which items failed.
            ServerStopError: If the server is running and fails to stop prior to deletion.
            AttributeError: If essential methods from other mixins (like `is_running` or `stop`)
                            are not available on the instance.
        """
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

        if getattr(self.app_context, "db", None) is not None:
            try:
                from ...db.models import Server, ServerBan

                async with self.app_context.db.session_manager() as db_session:
                    result = await db_session.execute(
                        select(Server).filter(Server.server_name == self.server_name)
                    )
                    db_server = result.scalars().first()
                    if db_server:
                        await db_session.execute(
                            delete(ServerBan).filter(
                                ServerBan.server_id == db_server.id
                            )
                        )
                        await db_session.delete(db_server)
                        await db_session.commit()

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
