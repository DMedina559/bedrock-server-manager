# bedrock_server_manager/core/server/installation_mixin.py
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
import shutil
import subprocess
from typing import Any, Dict, List, Optional

# Local application imports.
from bedrock_server_manager.core.server.base_server_mixin import BedrockServerBaseMixin
from bedrock_server_manager.core.system import base as system_base
from bedrock_server_manager.error import (
    AppFileNotFoundError,
    MissingArgumentError,
    FileOperationError,
    PermissionsError,
    ServerStopError,
)


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
        will be available on the composed :class:`~.core.bedrock_server.BedrockServer` object.

        Args:
            *args (Any): Variable length argument list passed to `super()`.
            **kwargs (Any): Arbitrary keyword arguments passed to `super()`.
        """
        super().__init__(*args, **kwargs)
        # Attributes from BedrockServerBaseMixin are available.
        # Methods from other mixins (e.g., ProcessMixin for stop/is_running)
        # are expected on the final composed BedrockServer object.

    def validate_installation(self) -> bool:
        """Validates that the server installation directory and executable exist.

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
            f"Validating installation for server '{self.server_name}' in directory: {self.server_dir}"
        )

        if not os.path.isdir(self.server_dir):
            raise AppFileNotFoundError(self.server_dir, "Server directory")

        if not os.path.isfile(self.bedrock_executable_path):
            raise AppFileNotFoundError(
                self.bedrock_executable_path, "Server executable"
            )

        self.logger.debug(
            f"Server '{self.server_name}' installation validation successful."
        )
        return True

    def is_installed(self) -> bool:
        """Checks if the server installation is valid, without raising exceptions.

        This is a convenience method that calls :meth:`.validate_installation`
        and catches :class:`~.error.AppFileNotFoundError` if validation fails,
        returning ``False`` in such cases.

        Returns:
            bool: ``True`` if the installation is valid (directory and executable exist),
            ``False`` otherwise.
        """
        try:
            return self.validate_installation()
        except AppFileNotFoundError:
            self.logger.debug(
                f"is_installed check: Server '{self.server_name}' not found or installation invalid (directory or executable missing)."
            )
            return False

    def set_filesystem_permissions(self) -> None:
        """Sets appropriate filesystem permissions for the server's installation directory.

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
        if (
            not self.is_installed()
        ):  # Ensures server_dir and executable exist before trying to set perms
            raise AppFileNotFoundError(
                self.server_dir,
                "Cannot set permissions: Server installation directory or executable not found",
            )

        self.logger.info(
            f"Setting filesystem permissions for server directory: {self.server_dir}"
        )
        try:
            system_base.set_server_folder_permissions(self.server_dir)
            self.logger.info(
                f"Successfully set permissions for server '{self.server_name}' at '{self.server_dir}'."
            )
        except (
            MissingArgumentError,
            AppFileNotFoundError,
            PermissionsError,
        ) as e_perm:  # Catch specific errors
            self.logger.error(
                f"Failed to set permissions for '{self.server_dir}': {e_perm}"
            )
            raise  # Re-raise the caught specific error
        except Exception as e_unexp:  # Catch any other unexpected error
            self.logger.error(
                f"Unexpected error setting permissions for '{self.server_name}': {e_unexp}",
                exc_info=True,
            )
            raise PermissionsError(
                f"Unexpected error setting permissions for server '{self.server_name}': {e_unexp}"
            ) from e_unexp

    def delete_server_files(
        self, item_description_prefix: str = "server installation files for"
    ) -> bool:
        """Deletes the server's entire installation directory (:attr:`.BedrockServerBaseMixin.server_dir`).

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
        self.logger.warning(
            f"DESTRUCTIVE ACTION: Attempting to delete all installation files for server '{self.server_name}' at: {self.server_dir}."
        )
        description = f"{item_description_prefix} server '{self.server_name}'"

        success = system_base.delete_path_robustly(self.server_dir, description)
        if success:
            self.logger.info(
                f"Successfully deleted server installation directory for '{self.server_name}'."
            )
        else:
            self.logger.error(
                f"Failed to fully delete server installation directory for '{self.server_name}'. Review logs for details."
            )
        return success

    def delete_all_data(self) -> None:
        """Deletes **ALL** data associated with this Bedrock server instance.

        .. danger::
            This is a **HIGHLY DESTRUCTIVE** operation and is irreversible.

            It removes:

                1. The server's main installation directory (:attr:`.BedrockServerBaseMixin.server_dir`).
                2. The server's JSON configuration subdirectory (:attr:`.BedrockServerBaseMixin.server_config_dir`).
                3. The server's entire backup directory (derived from ``paths.backups`` setting).
                4. The server's systemd user service file (on Linux systems only).
                5. The server's PID file.

        The method will attempt to stop a running server (using ``self.stop()``,
        expected from :class:`~.ServerProcessMixin`) before proceeding with deletions.
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
        # server_config_dir from BaseServerMixin is the server-specific one.
        server_json_config_subdir = self.server_config_dir

        backup_base_dir = self.settings.get("paths.backups")
        server_backup_dir_path = (
            os.path.join(backup_base_dir, self.server_name) if backup_base_dir else None
        )

        self.logger.warning(
            f"!!! DESTRUCTIVE ACTION: Preparing to delete ALL data for server '{self.server_name}' !!!"
        )
        self.logger.info(f"  - Target installation directory: {server_install_dir}")
        self.logger.info(
            f"  - Target JSON configuration directory: {server_json_config_subdir}"
        )
        if server_backup_dir_path:
            self.logger.info(f"  - Target backup directory: {server_backup_dir_path}")
        else:
            self.logger.info("  - No backup directory path configured or found.")

        # Check if any data exists to avoid unnecessary stop attempts if nothing to delete.
        paths_to_check_existence = [server_install_dir, server_json_config_subdir]
        if server_backup_dir_path:
            paths_to_check_existence.append(server_backup_dir_path)

        any_primary_data_exists = any(
            os.path.exists(p) for p in paths_to_check_existence if p
        )

        systemd_service_file_path: Optional[str] = None
        systemd_service_name = (
            f"bedrock-{self.server_name}.service"  # Ensure .service suffix
        )
        if self.os_type == "Linux":
            # Using the helper from linux.py now
            from . import (
                systemd_mixin,
            )  # Assuming it's in the same package or adjust import

            # This needs careful thought on how to access systemd_mixin or its functions here.
            # For now, let's assume a way to get this path, or directly use system_linux.get_systemd_user_service_file_path
            # For simplicity in this context, we'll re-construct it, but ideally, it would use a shared utility.
            try:
                from bedrock_server_manager.core.system import (
                    linux as system_linux,
                )  # Direct import

                systemd_service_file_path = (
                    system_linux.get_systemd_user_service_file_path(
                        systemd_service_name
                    )
                )
                if os.path.exists(systemd_service_file_path):
                    self.logger.info(
                        f"  - Target systemd service file: {systemd_service_file_path}"
                    )
                    any_primary_data_exists = True
            except Exception as e_sysd_path:
                self.logger.warning(
                    f"Could not determine systemd service file path for {systemd_service_name}: {e_sysd_path}"
                )

        if not any_primary_data_exists and not (
            systemd_service_file_path and os.path.exists(systemd_service_file_path)
        ):
            self.logger.info(
                f"No significant data or service files found for server '{self.server_name}'. Deletion considered complete."
            )
            return

        # Ensure the server is stopped before deleting its files.
        if not hasattr(self, "is_running") or not hasattr(self, "stop"):
            self.logger.warning(
                "'is_running' or 'stop' method not found on self. Cannot ensure server is stopped before deletion. This might indicate missing mixins."
            )
            # Depending on strictness, one might raise an error here.
        elif self.is_running():  # type: ignore
            self.logger.info(
                f"Server '{self.server_name}' is running. Attempting to stop it before deletion..."
            )
            try:
                self.stop()  # type: ignore
            except (
                ServerStopError
            ):  # Let ServerStopError propagate if stop fails critically
                raise
            except Exception as e_stop:  # Wrap other unexpected errors from stop()
                # Log as warning and proceed with deletion, as per original logic.
                self.logger.warning(
                    f"Failed to stop server '{self.server_name}' cleanly before deletion: {e_stop}. Proceeding with deletion, but the process might linger."
                )
        else:
            self.logger.info(
                f"Server '{self.server_name}' is not running. No stop needed."
            )

        deletion_errors: List[str] = []

        # --- 1. Remove systemd service (Linux-only) ---
        if (
            self.os_type == "Linux" and systemd_service_file_path
        ):  # systemd_service_file_path is now defined
            self.logger.info(
                f"Processing systemd user service '{systemd_service_name}'..."
            )
            # This part needs to call the systemd disabling/deletion logic,
            # potentially from a SystemdMixin or system_linux directly.
            # For now, just attempt to delete the file if systemctl interaction fails or isn't available.
            # A more robust implementation would involve a SystemdMixin.
            systemctl_cmd = shutil.which("systemctl")
            service_file_existed_before_systemctl = os.path.exists(
                systemd_service_file_path
            )

            if systemctl_cmd and service_file_existed_before_systemctl:
                try:
                    disable_cmds = [
                        systemctl_cmd,
                        "--user",
                        "disable",
                        "--now",
                        systemd_service_name,
                    ]
                    self.logger.debug(f"Executing: {' '.join(disable_cmds)}")
                    res_disable = subprocess.run(
                        disable_cmds,
                        check=False,
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                    )
                    if res_disable.returncode != 0 and not (
                        "doesn't exist" in res_disable.stderr.lower()
                        or "no such file" in res_disable.stderr.lower()
                    ):
                        self.logger.warning(
                            f"systemctl disable --now {systemd_service_name} failed: {res_disable.stderr.strip()}"
                        )

                    if os.path.exists(
                        systemd_service_file_path
                    ):  # File might still exist if disable failed or didn't remove it
                        if not system_base.delete_path_robustly(
                            systemd_service_file_path,
                            f"systemd service file for '{self.server_name}'",
                        ):
                            deletion_errors.append(
                                f"systemd service file '{systemd_service_file_path}'"
                            )

                    self.logger.debug(
                        "Reloading systemd user daemon and resetting failed units..."
                    )
                    subprocess.run(
                        [systemctl_cmd, "--user", "daemon-reload"],
                        check=False,
                        capture_output=True,
                    )
                    subprocess.run(
                        [systemctl_cmd, "--user", "reset-failed"],
                        check=False,
                        capture_output=True,
                    )
                    self.logger.info(
                        f"Systemd service '{systemd_service_name}' processing complete."
                    )

                except Exception as e_systemd:
                    self.logger.error(
                        f"Error managing systemd service '{systemd_service_name}': {e_systemd}",
                        exc_info=True,
                    )
                    deletion_errors.append(
                        f"systemd service interaction for '{systemd_service_name}'"
                    )
            elif (
                service_file_existed_before_systemctl
            ):  # systemctl not found but file exists
                self.logger.warning(
                    f"Systemd service file '{systemd_service_file_path}' exists but 'systemctl' not found. Deleting file directly."
                )
                if not system_base.delete_path_robustly(
                    systemd_service_file_path,
                    f"systemd service file (no systemctl) for '{self.server_name}'",
                ):
                    deletion_errors.append(
                        f"systemd service file '{systemd_service_file_path}' (no systemctl)"
                    )

        # --- 2. Remove PID file (using the method from BaseServerMixin) ---
        # get_pid_file_path should be available from BaseServerMixin
        if hasattr(self, "get_pid_file_path"):
            pid_file_to_delete = self.get_pid_file_path()  # type: ignore
            if os.path.exists(pid_file_to_delete):
                if not system_base.delete_path_robustly(
                    pid_file_to_delete, f"PID file for '{self.server_name}'"
                ):
                    deletion_errors.append(f"PID file '{pid_file_to_delete}'")
        else:
            self.logger.warning(
                "get_pid_file_path method not found. Cannot delete PID file by specific path."
            )

        # --- 3. Remove all directories ---
        paths_to_delete_map: Dict[str, Optional[str]] = {
            "backup": server_backup_dir_path,
            "installation": server_install_dir,
            "JSON configuration": server_json_config_subdir,  # server_config_dir from BaseServerMixin
        }
        for dir_type, dir_path_val in paths_to_delete_map.items():
            if dir_path_val and os.path.exists(
                dir_path_val
            ):  # Check if path is not None before os.path.exists
                if not system_base.delete_path_robustly(
                    dir_path_val, f"server {dir_type} data for '{self.server_name}'"
                ):
                    deletion_errors.append(f"{dir_type} directory '{dir_path_val}'")
            elif dir_path_val:  # Path was valid but didn't exist
                self.logger.debug(
                    f"Server {dir_type} data for '{self.server_name}' at '{dir_path_val}' not found, skipping deletion."
                )
            else:  # Path was None (e.g. backup_base_dir not configured)
                self.logger.debug(
                    f"Path for {dir_type} data for '{self.server_name}' was not configured. Skipping deletion."
                )

        # --- Final Check ---
        if deletion_errors:
            error_summary = "; ".join(deletion_errors)
            # Ensure status is set to ERROR if deletion wasn't clean
            if hasattr(self, "set_status_in_config"):
                self.set_status_in_config("ERROR")  # type: ignore
            raise FileOperationError(
                f"Failed to completely delete all data for server '{self.server_name}'. Failed items: {error_summary}"
            )
        else:
            self.logger.info(
                f"Successfully deleted all data for server: '{self.server_name}'."
            )
            # Set status to UNKNOWN or similar to indicate it's gone, if status methods are available
            if hasattr(self, "set_status_in_config"):
                self.set_status_in_config("DELETED")  # Or "UNKNOWN"
            if hasattr(self, "set_version"):
                self.set_version("UNKNOWN")  # type: ignore
