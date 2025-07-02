# bedrock_server_manager/core/server/backup_restore_mixin.py
"""Provides the :class:`.ServerBackupMixin` for the
:class:`~.core.bedrock_server.BedrockServer` class.

This mixin encapsulates all backup and restore operations for a Bedrock server
instance. Its responsibilities include:

    - Backing up the server's active world (as a ``.mcworld`` file) and key
      configuration files (``server.properties``, ``allowlist.json``,
      ``permissions.json``).
    - Listing available backups for different components (world, specific configs, or all).
    - Restoring the server's active world and configuration files from the latest
      available backups.
    - Pruning old backup files for each component based on retention policies
      defined in the application settings.

It relies on methods from other mixins, such as
:meth:`~.core.server.state_mixin.ServerStateMixin.get_world_name` to identify the active
world, and :class:`~.core.server.world_mixin.ServerWorldMixin` methods for world
export and import operations.
"""
import os
import glob
import re
import shutil
import logging
from typing import Optional, Dict, List, Union, Any

# Local application imports.
from bedrock_server_manager.core.server.base_server_mixin import BedrockServerBaseMixin
from bedrock_server_manager.error import (
    FileOperationError,
    UserInputError,
    BackupRestoreError,
    MissingArgumentError,
    ConfigurationError,
    AppFileNotFoundError,
    ExtractError,
)
from bedrock_server_manager.utils import (
    general,
)


class ServerBackupMixin(BedrockServerBaseMixin):
    """Provides methods for backing up, restoring, and pruning server data.

    This mixin extends :class:`.BedrockServerBaseMixin` and focuses on managing
    backups for a Bedrock server instance. This includes creating backups of
    the active world (as ``.mcworld`` files) and key configuration files
    (``server.properties``, ``allowlist.json``, ``permissions.json``).
    It also provides functionality to list available backups, restore from the
    latest ones, and prune old backups according to retention policies defined
    in the application settings (``retention.backups``).

    The mixin relies on:

        - Attributes from :class:`.BedrockServerBaseMixin` (e.g., `server_name`,
          `server_dir`, `settings`, `logger`).
        - Methods from :class:`~.core.server.state_mixin.ServerStateMixin` (e.g.,
          ``get_world_name()``) to identify the active world.
        - Methods from :class:`~.core.server.world_mixin.ServerWorldMixin` (e.g.,
          ``export_world_directory_to_mcworld()``, ``import_active_world_from_mcworld()``)
          for world archiving and extraction.

    Properties:
        server_backup_directory (Optional[str]): The path to this server's specific backup directory.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initializes the ServerBackupMixin.

        Calls ``super().__init__(*args, **kwargs)`` to participate in cooperative
        multiple inheritance. It depends on attributes initialized by
        :class:`.BedrockServerBaseMixin` and assumes methods from other mixins
        (like :meth:`~.core.server.state_mixin.ServerStateMixin.get_world_name`,
        :meth:`~.core.server.world_mixin.ServerWorldMixin.export_world_directory_to_mcworld`,
        and :meth:`~.core.server.world_mixin.ServerWorldMixin.import_active_world_from_mcworld`)
        will be available on the composed :class:`~.core.bedrock_server.BedrockServer` object.

        Args:
            *args (Any): Variable length argument list passed to `super()`.
            **kwargs (Any): Arbitrary keyword arguments passed to `super()`.
        """
        super().__init__(*args, **kwargs)
        # Dependencies on other mixins' methods are resolved at runtime on the
        # final BedrockServer class instance.

    @property
    def server_backup_directory(self) -> Optional[str]:
        """Optional[str]: The absolute path to this server's specific backup directory.

        This path is constructed by joining the global backup directory path
        (from ``settings.get("paths.backups")``) with the server's name
        (:attr:`~.BedrockServerBaseMixin.server_name`).
        The directory itself is created by backup methods if it doesn't exist.

        Returns:
            The absolute path to the backup directory if ``paths.backups`` is
            configured in settings, otherwise ``None`` (and a warning is logged).
        """
        backup_base_dir = self.settings.get("paths.backups")
        if not backup_base_dir:
            self.logger.warning(
                f"Global backup directory ('paths.backups') not configured in settings. "
                f"Cannot determine backup directory for server '{self.server_name}'."
            )
            return None
        return os.path.join(
            str(backup_base_dir), self.server_name
        )  # Ensure backup_base_dir is str

    @staticmethod
    def _find_and_sort_backups(pattern: str) -> List[str]:
        """Finds files matching a glob pattern and sorts them by modification time (newest first).

        This static utility method is used to find backup files (e.g., based on
        a pattern like ``*.mcworld`` or ``server_backup_*.properties``) and sort
        them so the most recent backups appear first in the list.

        Args:
            pattern (str): The glob pattern to search for files (e.g.,
                ``/path/to/backups/MyWorld_backup_*.mcworld``).

        Returns:
            List[str]: A list of absolute file paths matching the pattern, sorted
            by modification time in descending order (newest first). Returns an
            empty list if no files match the pattern.
        """
        files = glob.glob(pattern)
        if not files:
            return []
        # Sort by modification time, descending (newest first).
        return sorted(files, key=os.path.getmtime, reverse=True)

    def list_backups(self, backup_type: str) -> Union[List[str], Dict[str, List[str]]]:
        """Retrieves a list of available backup files for this server, sorted newest first.

        This method scans the server's specific backup directory (obtained via
        :attr:`.server_backup_directory`) for backup files matching the
        specified ``backup_type``. Backups are sorted by their modification time,
        with the most recent backup appearing first.

        Valid ``backup_type`` options (case-insensitive):

            - ``"world"``: Lists ``*.mcworld`` files (world backups).
            - ``"properties"``: Lists ``server_backup_*.properties`` files.
            - ``"allowlist"``: Lists ``allowlist_backup_*.json`` files.
            - ``"permissions"``: Lists ``permissions_backup_*.json`` files.
            - ``"all"``: Returns a dictionary categorizing all found backup types.

        Args:
            backup_type (str): The type of backups to list. Must be one of
                "world", "properties", "allowlist", "permissions", or "all".

        Returns:
            Union[List[str], Dict[str, List[str]]]:

                - If ``backup_type`` is specific (e.g., "world"), returns a list of
                  absolute backup file paths, sorted by modification time (newest first).
                  An empty list is returned if no matching backups are found or if the
                  server's backup directory doesn't exist.
                - If ``backup_type`` is "all", returns a dictionary where keys are backup
                  categories (e.g., "world_backups", "properties_backups") and values
                  are the corresponding sorted lists of file paths. An empty dictionary
                  is returned if the backup directory doesn't exist or no backups of
                  any type are found.

        Raises:
            MissingArgumentError: If ``backup_type`` is empty or not a string.
            UserInputError: If ``backup_type`` is not one of the valid options.
            ConfigurationError: If the server's backup directory is not configured
                (i.e., :attr:`.server_backup_directory` is ``None``).
            FileOperationError: If an ``OSError`` occurs during filesystem listing
                (e.g., permission issues).
        """
        if not isinstance(backup_type, str) or not backup_type:
            raise MissingArgumentError(
                "Backup type cannot be empty and must be a string."
            )

        server_bck_dir = self.server_backup_directory
        if not server_bck_dir:
            raise ConfigurationError(
                f"Cannot list backups for '{self.server_name}': Backup directory not configured."
            )

        backup_type_norm = backup_type.lower()
        self.logger.info(
            f"Server '{self.server_name}': Listing '{backup_type_norm}' backups from '{server_bck_dir}'."
        )

        if not os.path.isdir(server_bck_dir):
            self.logger.warning(
                f"Backup directory not found: '{server_bck_dir}'. Returning empty result."
            )
            return {} if backup_type_norm == "all" else []

        try:
            # Define glob patterns for each type of backup.
            patterns = {
                "world": os.path.join(
                    server_bck_dir, "*.mcworld"
                ),  # Standard .mcworld extension
                "properties": os.path.join(
                    server_bck_dir, "server_backup_*.properties"
                ),
                "allowlist": os.path.join(server_bck_dir, "allowlist_backup_*.json"),
                "permissions": os.path.join(
                    server_bck_dir, "permissions_backup_*.json"
                ),
            }

            if backup_type_norm in patterns:
                return self._find_and_sort_backups(patterns[backup_type_norm])
            elif backup_type_norm == "all":
                categorized_backups: Dict[str, List[str]] = {}
                for key, pattern in patterns.items():
                    files = self._find_and_sort_backups(pattern)
                    if files:  # Only add category if backups exist
                        categorized_backups[f"{key}_backups"] = files
                return categorized_backups
            else:
                valid_types = list(patterns.keys()) + ["all"]
                raise UserInputError(
                    f"Invalid backup type: '{backup_type}'. Must be one of {valid_types}."
                )

        except (
            OSError
        ) as e:  # Catch errors from os.path.isdir, glob.glob, os.path.getmtime
            raise FileOperationError(
                f"Error listing backups for '{self.server_name}' due to a filesystem issue: {e}"
            ) from e

    def prune_server_backups(self, component_prefix: str, file_extension: str) -> None:
        """Removes the oldest backups for a specific component to adhere to retention policies.

        This method targets backup files within this server's specific backup directory

        (see :attr:`.server_backup_directory`) that match a given ``component_prefix``
        (e.g., ``MyActiveWorld_backup_``, ``server_backup_``) and ``file_extension``
        (e.g., ``mcworld``, ``properties``, ``json``).

        It retrieves the number of backups to keep from the application settings
        (key: ``retention.backups``, defaulting to 3 if not set or invalid). If more
        backups than this configured number are found (sorted by modification time),
        the oldest ones are deleted until the retention count is met.

        Args:
            component_prefix (str): The prefix part of the backup filenames to
                target (e.g., ``MyActiveWorld_backup_`` for world backups,
                ``server_backup_`` for server.properties backups). Should not be empty.
            file_extension (str): The extension of the backup files, without the
                leading dot (e.g., "mcworld", "json", "properties"). Should not be empty.

        Raises:
            ConfigurationError: If the server's backup directory path
                (:attr:`.server_backup_directory`) is not configured in settings.
            MissingArgumentError: If ``component_prefix`` or ``file_extension``
                are empty or not strings.
            UserInputError: If the ``retention.backups`` setting value from application
                settings is invalid (e.g., not a non-negative integer).
            FileOperationError: If an ``OSError`` occurs during file listing or deletion
                (e.g., permission issues), or if not all required old backups
                could be deleted successfully.
        """
        server_bck_dir = self.server_backup_directory
        if not server_bck_dir:
            raise ConfigurationError(
                f"Cannot prune backups for '{self.server_name}': Server backup directory path is not configured."
            )

        if not isinstance(component_prefix, str) or not component_prefix.strip():
            raise MissingArgumentError("component_prefix must be a non-empty string.")
        if not isinstance(file_extension, str) or not file_extension.strip():
            raise MissingArgumentError("file_extension must be a non-empty string.")

        backup_keep_count = self.settings.get("retention.backups", 3)  # Default to 3

        self.logger.info(
            f"Server '{self.server_name}': Pruning backups in '{server_bck_dir}' for prefix '{component_prefix}', "
            f"extension '{file_extension}', configured to keep {backup_keep_count}."
        )

        if not os.path.isdir(server_bck_dir):
            self.logger.info(
                f"Backup directory '{server_bck_dir}' for server '{self.server_name}' not found. Nothing to prune."
            )
            return  # Nothing to do if the directory doesn't exist

        try:
            num_to_keep = int(backup_keep_count)
            if num_to_keep < 0:  # Allowing 0 means delete all but 0 (i.e., delete all)
                raise ValueError("Retention count cannot be negative.")
        except (ValueError, TypeError) as e_val:
            raise UserInputError(
                f"Invalid 'retention.backups' setting value: '{backup_keep_count}'. Must be a non-negative integer."
            ) from e_val

        cleaned_ext = file_extension.lstrip(".").strip()
        if not cleaned_ext:  # Should have been caught by initial check, but defensive
            raise MissingArgumentError(
                "File extension cannot be effectively empty after stripping dots."
            )

        # Glob pattern needs to be precise. Example: server_backup_*.properties, MyWorld_backup_*.mcworld
        glob_pattern = os.path.join(
            server_bck_dir, f"{component_prefix}*.{cleaned_ext}"
        )
        self.logger.debug(f"Using glob pattern for pruning backups: '{glob_pattern}'")

        try:
            # Find and sort backups: newest first, oldest will be at the end.
            backup_files = self._find_and_sort_backups(
                glob_pattern
            )  # Uses mtime, newest first

            if len(backup_files) > num_to_keep:
                # Files to delete are those beyond the num_to_keep threshold, from the end of the sorted list (oldest)
                files_to_delete = backup_files[
                    num_to_keep:
                ]  # Slicing from num_to_keep to end gets the oldest
                self.logger.info(
                    f"Found {len(backup_files)} backups for '{component_prefix}*.{cleaned_ext}'. "
                    f"Will delete {len(files_to_delete)} oldest file(s) to keep {num_to_keep}."
                )
                deleted_count = 0
                failed_deletions: List[str] = []  # Store paths of failed deletions
                for old_backup_path in files_to_delete:
                    try:
                        self.logger.debug(f"Removing old backup: {old_backup_path}")
                        os.remove(old_backup_path)
                        deleted_count += 1
                    except OSError as e_del:
                        self.logger.error(
                            f"Failed to remove old backup '{old_backup_path}': {e_del}"
                        )
                        failed_deletions.append(
                            str(old_backup_path)
                        )  # Convert Path to str if it's Path

                if failed_deletions:
                    # If some deletions failed, this is an issue.
                    raise FileOperationError(
                        f"Failed to delete {len(failed_deletions)} required old backup(s) for '{component_prefix}' "
                        f"for server '{self.server_name}'. Failed paths: {', '.join(failed_deletions)}"
                    )
                if (
                    deleted_count > 0
                ):  # Log success only if something was actually deleted
                    self.logger.info(
                        f"Successfully deleted {deleted_count} old backup(s)."
                    )

            else:
                self.logger.info(
                    f"Found {len(backup_files)} backups for '{component_prefix}*.{cleaned_ext}', "
                    f"which is not more than the {num_to_keep} to keep. No files were deleted."
                )
        except OSError as e_glob:  # Errors from glob.glob or os.path.getmtime
            raise FileOperationError(
                f"Error accessing or processing backup files for pruning for server '{self.server_name}': {e_glob}"
            ) from e_glob

    def _backup_world_data_internal(self) -> str:
        """Orchestrates the backup of the server's active world to a ``.mcworld`` file.

        This internal helper performs the following sequence:

            1. Retrieves the active world name using ``self.get_world_name()`` (from
               :class:`~.core.server.state_mixin.ServerStateMixin`).
            2. Ensures the server's specific backup directory (derived from
               :attr:`.server_backup_directory`) exists, creating it if necessary.
            3. Constructs a timestamped backup filename, e.g.,
               ``<SafeWorldName>_backup_YYYYMMDD_HHMMSS.mcworld``.
               The world name is sanitized for filesystem compatibility.
            4. Invokes ``self.export_world_directory_to_mcworld()`` (from
               :class:`~.core.server.world_mixin.ServerWorldMixin`) to create the
               ``.mcworld`` archive in the backup directory.
            5. After successful archive creation, it calls :meth:`.prune_server_backups`
               to remove older world backups, adhering to the configured retention policy.

        Returns:
            str: The absolute path to the created ``.mcworld`` backup file.

        Raises:
            ConfigurationError: If the server's backup directory path
                (:attr:`.server_backup_directory`) is not configured in settings.
            AppFileNotFoundError: If the active world's directory (determined via
                ``get_world_name()``) does not exist or is inaccessible.
            FileOperationError: For general file I/O errors during backup directory
                creation or if ``self.export_world_directory_to_mcworld()`` fails
                due to filesystem issues (e.g., permissions, disk full).
            BackupRestoreError: If the world export process itself
                (``self.export_world_directory_to_mcworld()``) reports a failure
                (e.g., issues with ``.mcworld`` creation).
            AttributeError: If ``get_world_name()`` or
                ``export_world_directory_to_mcworld()`` methods are not available
                on the server instance (indicating missing or incorrectly configured
                :class:`~.core.server.state_mixin.ServerStateMixin` or
                :class:`~.core.server.world_mixin.ServerWorldMixin`).
        """
        if not hasattr(self, "get_world_name") or not hasattr(
            self, "export_world_directory_to_mcworld"
        ):
            self.logger.error(
                "Missing required methods (get_world_name or export_world_directory_to_mcworld) for world backup."
            )
            raise AttributeError(
                "Required world management methods are missing from this server instance."
            )

        active_world_name: str = self.get_world_name()  # type: ignore
        active_world_dir_path = os.path.join(  # For logging/validation, export_world_directory_to_mcworld uses world_dir_name
            self.server_dir, "worlds", active_world_name
        )

        server_bck_dir = self.server_backup_directory
        if not server_bck_dir:
            raise ConfigurationError(
                f"Cannot backup world for '{self.server_name}': Backup directory not configured."
            )

        self.logger.info(
            f"Server '{self.server_name}': Starting backup for world '{active_world_name}' from '{active_world_dir_path}'."
        )

        if not os.path.isdir(active_world_dir_path):
            raise AppFileNotFoundError(active_world_dir_path, "Active world directory")

        os.makedirs(server_bck_dir, exist_ok=True)

        timestamp = general.get_timestamp()
        # Sanitize the world name to ensure it's a valid filename component.
        safe_world_name_for_file = re.sub(r'[<>:"/\\|?*]', "_", active_world_name)
        backup_filename = f"{safe_world_name_for_file}_backup_{timestamp}.mcworld"
        backup_file_path = os.path.join(server_bck_dir, backup_filename)

        self.logger.info(
            f"Creating world backup: '{backup_filename}' in '{server_bck_dir}'..."
        )
        try:
            # This method is expected to be on the final class from WorldMixin.
            self.export_world_directory_to_mcworld(active_world_name, backup_file_path)  # type: ignore
            self.logger.info(
                f"World backup for '{self.server_name}' created: {backup_file_path}"
            )
            # Prune old backups after a new one is successfully created.
            self.prune_server_backups(f"{safe_world_name_for_file}_backup_", "mcworld")
            return backup_file_path
        except (
            BackupRestoreError,
            FileOperationError,
            AppFileNotFoundError,
        ) as e_export:
            self.logger.error(
                f"Failed to export world '{active_world_name}' for server '{self.server_name}': {e_export}",
                exc_info=True,
            )
            raise
        except Exception as e_unexp:  # Catch any other unexpected errors during export
            raise FileOperationError(
                f"Unexpected error exporting world '{active_world_name}' for '{self.server_name}': {e_unexp}"
            ) from e_unexp

    def _backup_config_file_internal(
        self, config_filename_in_server_dir: str
    ) -> Optional[str]:
        """Backs up a single specified server configuration file with a timestamp.

        This helper copies a configuration file (e.g., "server.properties",
        "allowlist.json") from the server's main installation directory
        (:attr:`~.BedrockServerBaseMixin.server_dir`) to the server's specific
        backup directory (:attr:`.server_backup_directory`). The backup directory
        is created if it doesn't exist.

        The backup file is named using the pattern:
        ``<original_name>_backup_YYYYMMDD_HHMMSS.<original_ext>``.
        For instance, "server.properties" becomes
        "server_backup_20230101_120000.properties".

        After a successful backup, it calls :meth:`.prune_server_backups` for this
        specific configuration file type to manage retention of older backups
        according to application settings.

        Args:
            config_filename_in_server_dir (str): The name of the configuration
                file (e.g., "server.properties") located in the server's
                installation directory, which is to be backed up.

        Returns:
            Optional[str]: The absolute path to the created backup file if the
            original file exists and the backup is successful. Returns ``None`` if
            the original configuration file is not found in the server directory
            (a warning is logged in this case, and no backup is attempted).

        Raises:
            ConfigurationError: If the server's backup directory path
                (:attr:`.server_backup_directory`) is not configured in settings.
            FileOperationError: If the file copy operation (``shutil.copy2``) fails
                during backup (e.g., due to permissions or disk I/O issues), or
                if creating the backup directory fails.
        """
        file_to_backup_path = os.path.join(
            self.server_dir, config_filename_in_server_dir
        )

        server_bck_dir = self.server_backup_directory
        if not server_bck_dir:
            raise ConfigurationError(
                f"Cannot backup config for '{self.server_name}': Backup directory not configured."
            )

        self.logger.info(
            f"Server '{self.server_name}': Starting backup for config file '{config_filename_in_server_dir}'."
        )

        if not os.path.isfile(file_to_backup_path):
            self.logger.warning(
                f"Config file '{config_filename_in_server_dir}' not found at '{file_to_backup_path}'. Skipping backup."
            )
            return None

        os.makedirs(server_bck_dir, exist_ok=True)  # Ensures backup directory exists

        name_part, ext_part = os.path.splitext(config_filename_in_server_dir)
        timestamp = general.get_timestamp()  # YYYYMMDD_HHMMSS format
        backup_config_filename = f"{name_part}_backup_{timestamp}{ext_part}"
        backup_destination_path = os.path.join(server_bck_dir, backup_config_filename)

        try:
            # copy2 preserves metadata like modification time.
            shutil.copy2(file_to_backup_path, backup_destination_path)
            self.logger.info(
                f"Config file '{config_filename_in_server_dir}' backed up to '{backup_destination_path}'."
            )
            # Prune old backups of this specific config file.
            self.prune_server_backups(f"{name_part}_backup_", ext_part.lstrip("."))
            return backup_destination_path
        except OSError as e:  # Covers errors from shutil.copy2
            raise FileOperationError(
                f"Failed to copy config '{config_filename_in_server_dir}' for '{self.server_name}' to backup: {e}"
            ) from e

    def backup_all_data(self) -> Dict[str, Optional[str]]:
        """Performs a full backup of the server's active world and standard configuration files.

        This method orchestrates the backup of the following components:

            - The active world: Determined by ``self.get_world_name()`` (from
              :class:`~.core.server.state_mixin.ServerStateMixin`), then backed up to
              a ``.mcworld`` file via :meth:`._backup_world_data_internal`.
            - ``allowlist.json``: Backed up via :meth:`._backup_config_file_internal`.
            - ``permissions.json``: Backed up via :meth:`._backup_config_file_internal`.
            - ``server.properties``: Backed up via :meth:`._backup_config_file_internal`.

        Each component is backed up individually. The server's specific backup
        directory (derived from :attr:`.server_backup_directory`) is created if it
        doesn't already exist.

        If the critical world backup fails, a :class:`~.error.BackupRestoreError`
        is raised *after* attempting to back up all configuration files. Failures
        in backing up individual configuration files are logged as errors, and their
        corresponding entry in the returned dictionary will be ``None``, but they
        do not stop the backup of other components.

        Returns:
            Dict[str, Optional[str]]: A dictionary mapping component names
            (e.g., "world", "allowlist.json") to the absolute path of their
            backup file. If a component's backup failed or was skipped (e.g.,
            the original file was not found), its value will be ``None``.

        Raises:
            ConfigurationError: If the server's backup directory path
                (:attr:`.server_backup_directory`) is not configured in settings.
            FileOperationError: If creation of the main server backup directory
                (under the global backup path) fails.
            BackupRestoreError: If the critical world backup operation fails.
                                Other underlying errors from helper methods
                                (like :class:`~.error.AppFileNotFoundError` from
                                :meth:`._backup_world_data_internal` if the world
                                directory is missing) can also propagate.
            AttributeError: If required methods from other mixins (e.g.,
                ``get_world_name()`` from :class:`~.core.server.state_mixin.ServerStateMixin`
                or ``export_world_directory_to_mcworld()`` from
                :class:`~.core.server.world_mixin.ServerWorldMixin`) are not available.
        """
        server_bck_dir = self.server_backup_directory
        if not server_bck_dir:
            raise ConfigurationError(
                f"Cannot backup server '{self.server_name}': Server backup directory path is not configured."
            )

        # Ensure the main backup directory for this server exists.
        try:
            os.makedirs(server_bck_dir, exist_ok=True)
        except OSError as e_mkdir:
            raise FileOperationError(
                f"Failed to create server backup directory '{server_bck_dir}' for server '{self.server_name}': {e_mkdir}"
            ) from e_mkdir

        self.logger.info(
            f"Server '{self.server_name}': Starting full backup into '{server_bck_dir}'."
        )
        backup_results: Dict[str, Optional[str]] = {}
        world_backup_failed = False

        try:
            backup_results["world"] = self._backup_world_data_internal()
        except Exception as e_world:  # Catch broadly as world backup is critical
            self.logger.error(
                f"CRITICAL: World backup failed for server '{self.server_name}': {e_world}",
                exc_info=True,
            )
            backup_results["world"] = None
            world_backup_failed = True  # Flag critical failure

        config_files_to_backup = [
            "allowlist.json",
            "permissions.json",
            "server.properties",
        ]
        for conf_file in config_files_to_backup:
            try:
                backup_results[conf_file] = self._backup_config_file_internal(conf_file)
            except Exception as e_conf:  # Catch broadly for individual config files
                self.logger.error(
                    f"Failed to back up configuration file '{conf_file}' for server '{self.server_name}': {e_conf}",
                    exc_info=True,
                )
                backup_results[conf_file] = None  # Mark as failed but continue

        if world_backup_failed:
            # Raise after attempting all other backups if world backup (most critical) failed.
            raise BackupRestoreError(
                f"Core world backup failed for server '{self.server_name}'. "
                "Other configuration file backups may or may not have succeeded. Check logs."
            )

        self.logger.info(
            f"Full backup for server '{self.server_name}' completed. Results: {backup_results}"
        )
        return backup_results

    def _restore_config_file_internal(self, backup_config_file_path: str) -> str:
        """Restores a single server configuration file from a specific backup file path.

        This helper takes the absolute path to a backup file (e.g.,
        ``.../backups/MyServer/server_backup_20230101_120000.properties``).
        It parses this filename to determine the original name of the configuration
        file (e.g., ``server.properties`` by stripping the ``_backup_YYYYMMDD_HHMMSS``
        part).

        It then copies the backup file to the server's main installation directory
        (:attr:`~.BedrockServerBaseMixin.server_dir`), renaming it to its original
        filename and overwriting any existing file at that location. The server's
        installation directory is created if it doesn't exist.

        Args:
            backup_config_file_path (str): The absolute path to the backup
                configuration file that should be restored.

        Returns:
            str: The absolute path where the configuration file was restored
            (e.g., ``<server_dir>/server.properties``).

        Raises:
            AppFileNotFoundError: If the ``backup_config_file_path`` does not
                exist or is not a regular file.
            UserInputError: If the backup filename does not conform to the expected
                timestamped format (``<original_name>_backup_YYYYMMDD_HHMMSS.ext``),
                which prevents determination of the original filename.
            FileOperationError: If ensuring the server directory exists or copying
                the file (via ``shutil.copy2``) fails (e.g., due to
                permission issues or disk errors).
        """
        backup_filename_basename = os.path.basename(backup_config_file_path)
        self.logger.info(
            f"Server '{self.server_name}': Restoring config from backup '{backup_filename_basename}'."
        )

        if not os.path.isfile(backup_config_file_path):
            raise AppFileNotFoundError(backup_config_file_path, "Backup config file")

        # Ensure server directory exists before restoring into it.
        try:
            os.makedirs(self.server_dir, exist_ok=True)
        except OSError as e_mkdir:
            raise FileOperationError(
                f"Failed to ensure server directory '{self.server_dir}' exists for restore: {e_mkdir}"
            ) from e_mkdir

        # Regex to extract original name: (name_part)_backup_YYYYMMDD_HHMMSS(.ext_part).
        # Example: "server_backup_20230101_120000.properties" -> ("server", ".properties")
        match = re.match(r"^(.*?)_backup_\d{8}_\d{6}(\..*)$", backup_filename_basename)
        if not match:
            raise UserInputError(
                f"Could not determine original filename from backup format: '{backup_filename_basename}'. "
                "Expected format: <original_name>_backup_YYYYMMDD_HHMMSS.ext"
            )

        original_name_part, original_ext_part = match.group(1), match.group(2)
        target_filename_in_server = f"{original_name_part}{original_ext_part}"
        target_restore_path = os.path.join(self.server_dir, target_filename_in_server)

        self.logger.info(
            f"Restoring '{backup_filename_basename}' as '{target_filename_in_server}' into '{self.server_dir}'..."
        )
        try:
            shutil.copy2(backup_config_file_path, target_restore_path)
            self.logger.info(f"Successfully restored config to: {target_restore_path}")
            return target_restore_path
        except OSError as e_copy:  # Covers errors from shutil.copy2
            raise FileOperationError(
                f"Failed to restore config '{target_filename_in_server}' for server '{self.server_name}' from backup: {e_copy}"
            ) from e_copy

    def restore_all_data_from_latest(self) -> Dict[str, Optional[str]]:
        """Restores the server's active world and standard configuration files from their latest backups.

        This method attempts to restore the following components by finding their
        most recent backup file (sorted by modification time) in the server's
        specific backup directory (see :attr:`.server_backup_directory`):

            - The active world: Restored using
              :meth:`~.core.server.world_mixin.ServerWorldMixin.import_active_world_from_mcworld`
              after finding the latest ``.mcworld`` backup matching the active world's name.
            - ``server.properties``: Restored via :meth:`._restore_config_file_internal`.
            - ``allowlist.json``: Restored via :meth:`._restore_config_file_internal`.
            - ``permissions.json``: Restored via :meth:`._restore_config_file_internal`.

        Each component is restored individually. If a backup for a specific component
        is not found, or if the restore operation for that component fails, the issue
        is logged, and the process continues with other components.
        A :class:`~.error.BackupRestoreError` is raised at the end if any component
        failed to restore, summarizing all failures.

        The server's main installation directory (:attr:`~.BedrockServerBaseMixin.server_dir`)
        is created if it doesn't exist before attempting to restore files into it.

        .. warning::
            This operation **overwrites** current world data and configuration files
            in the server's installation directory with content from the backups.
            Ensure this is the desired action before proceeding.

        Returns:
            Dict[str, Optional[str]]: A dictionary mapping component names (e.g., "world",
            "server.properties") to the absolute path where they were restored in
            the server's installation directory. If a component's restore was skipped
            (e.g., no backup found) or failed, its value in the dictionary will be ``None``.
            Returns an empty dictionary if the server's backup directory itself is
            not found or is inaccessible.

        Raises:
            ConfigurationError: If the server's backup directory path
                (:attr:`.server_backup_directory`) is not configured in settings.
            FileOperationError: If creation of the server's main installation directory
                (``self.server_dir``) fails.
            BackupRestoreError: If one or more components (world or configuration files)
                                fail to restore. The error message will summarize all failures.
            AttributeError: If required methods from other mixins (e.g.,
                ``get_world_name()`` or ``import_active_world_from_mcworld()``)
                are not available on the server instance.
        """
        server_bck_dir = self.server_backup_directory
        if not server_bck_dir or not os.path.isdir(
            server_bck_dir
        ):  # Check existence of backup dir
            self.logger.warning(
                f"No backup directory found for server '{self.server_name}' at '{server_bck_dir}'. Cannot restore."
            )
            return {}  # Return empty if backup source is unavailable

        self.logger.info(
            f"Server '{self.server_name}': Starting restore of all data from latest backups in '{server_bck_dir}'."
        )
        # Ensure server's main installation directory exists before restoring into it.
        try:
            os.makedirs(self.server_dir, exist_ok=True)
        except OSError as e_mkdir:
            raise FileOperationError(
                f"Failed to ensure server directory '{self.server_dir}' exists for restore: {e_mkdir}"
            ) from e_mkdir

        restore_results: Dict[str, Optional[str]] = {}
        failures: List[str] = (
            []
        )  # To collect names of components that failed to restore

        # Restore World
        try:
            if not hasattr(self, "get_world_name") or not hasattr(
                self, "import_active_world_from_mcworld"
            ):
                raise AttributeError(
                    "Missing get_world_name or import_active_world_from_mcworld method for world restore."
                )

            world_backup_files = self._find_and_sort_backups(
                os.path.join(server_bck_dir, "*.mcworld")
            )  # Newest first

            # Filter for backups matching the current active world name.
            # Assumes backups are named like <world_name>_backup_timestamp.mcworld
            active_world_name: str = self.get_world_name()  # type: ignore
            # Sanitize world name for matching backup file prefixes
            safe_world_name_prefix = (
                re.sub(r'[<>:"/\\|?*]', "_", active_world_name) + "_backup_"
            )

            relevant_world_backups = [
                f
                for f in world_backup_files
                if os.path.basename(f).startswith(safe_world_name_prefix)
            ]

            if relevant_world_backups:
                latest_world_backup_path = relevant_world_backups[
                    0
                ]  # First one is newest due to sort
                self.logger.info(
                    f"Found latest world backup for '{active_world_name}': {os.path.basename(latest_world_backup_path)}"
                )
                # import_active_world_from_mcworld is expected from WorldMixin
                imported_world_name_check = self.import_active_world_from_mcworld(latest_world_backup_path)  # type: ignore
                # The path stored should be the actual world path in the server directory, not the backup path
                restore_results["world"] = os.path.join(
                    self.server_dir, "worlds", imported_world_name_check
                )
                self.logger.info(
                    f"World '{active_world_name}' restored successfully from '{os.path.basename(latest_world_backup_path)}'."
                )
            else:
                self.logger.info(
                    f"No .mcworld backups found specifically for active world '{active_world_name}' of server '{self.server_name}'. Skipping world restore."
                )
                restore_results["world"] = None
        except Exception as e_world_restore:  # Catch broad exceptions for world restore
            self.logger.error(
                f"Failed to restore world for server '{self.server_name}': {e_world_restore}",
                exc_info=True,
            )
            failures.append(f"World ({type(e_world_restore).__name__})")
            restore_results["world"] = None

        # Restore standard configuration files
        config_files_to_restore = [
            "server.properties",
            "allowlist.json",
            "permissions.json",
        ]
        for original_conf_name in config_files_to_restore:
            try:
                name_part, ext_part = os.path.splitext(original_conf_name)
                backup_prefix = f"{name_part}_backup_"  # e.g., "server_backup_"
                backup_extension = ext_part.lstrip(".")  # e.g., "properties"

                # Find backups for this specific config file type, sorted newest first
                candidate_backups = self._find_and_sort_backups(
                    os.path.join(server_bck_dir, f"{backup_prefix}*.{backup_extension}")
                )

                if candidate_backups:
                    latest_config_backup_path = candidate_backups[0]  # Newest is first
                    self.logger.info(
                        f"Found latest backup for '{original_conf_name}': {os.path.basename(latest_config_backup_path)}"
                    )
                    restored_config_path = self._restore_config_file_internal(
                        latest_config_backup_path
                    )
                    restore_results[original_conf_name] = restored_config_path
                else:
                    self.logger.info(
                        f"No backups found for '{original_conf_name}' for server '{self.server_name}'. Skipping restore."
                    )
                    restore_results[original_conf_name] = None
            except (
                Exception
            ) as e_conf_restore:  # Catch broad exceptions for each config file
                self.logger.error(
                    f"Failed to restore '{original_conf_name}' for server '{self.server_name}': {e_conf_restore}",
                    exc_info=True,
                )
                failures.append(
                    f"{original_conf_name} ({type(e_conf_restore).__name__})"
                )
                restore_results[original_conf_name] = None

        if failures:
            # If any component failed to restore, raise an error summarizing them.
            raise BackupRestoreError(
                f"Restore for server '{self.server_name}' completed with errors for component(s): {', '.join(failures)}"
            )

        self.logger.info(
            f"Restore process from latest backups completed for server '{self.server_name}'."
        )
        return restore_results
