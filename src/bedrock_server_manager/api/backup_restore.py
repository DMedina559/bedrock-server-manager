# bedrock_server_manager/api/backup_restore.py
"""Provides API functions for server backup, restore, and pruning operations.

This module offers a high-level interface for managing the backup and restoration
of Bedrock server data. It orchestrates calls to methods of the
:class:`~bedrock_server_manager.core.bedrock_server.BedrockServer` class,
primarily those provided by the
:class:`~bedrock_server_manager.core.server.backup_restore_mixin.ServerBackupMixin`.

Key functionalities include:
    - Listing available backup files (:func:`~.list_backup_files`).
    - Backing up individual components like the server world (:func:`~.backup_world`)
      or specific configuration files (:func:`~.backup_config_file`).
    - Performing a comprehensive backup of all standard server data (:func:`~.backup_all`).
    - Restoring all server data from the latest available backups (:func:`~.restore_all`).
    - Restoring the server world from a specific ``.mcworld`` file (:func:`~.restore_world`).
    - Restoring a specific configuration file from its backup (:func:`~.restore_config_file`).
    - Pruning old backups based on retention policies (:func:`~.prune_old_backups`).

Operations involving file modifications are thread-safe using a unified lock
(``_backup_restore_lock``). For actions requiring the server to be offline,
this module utilizes the
:func:`~bedrock_server_manager.api.utils.server_lifecycle_manager`
to safely stop and restart the server. All functions are exposed to the plugin system.
"""
import os
import logging
import threading
from typing import Dict, Any, Optional

# Plugin system imports to bridge API functionality.
from ..plugins import plugin_method

# Local application imports.
from .utils import server_lifecycle_manager
from ..plugins.event_trigger import trigger_plugin_event
from ..error import (
    BSMError,
    AppFileNotFoundError,
    MissingArgumentError,
    InvalidServerNameError,
)
from ..context import AppContext

logger = logging.getLogger(__name__)

# A unified lock for all backup, restore, and prune operations.
# This ensures that only one file-modifying operation can run at a time across
# the entire module, preventing race conditions and potential data corruption.
_backup_restore_lock = threading.Lock()


@plugin_method("list_backup_files")
def list_backup_files(
    server_name: str, backup_type: str, app_context: AppContext
) -> Dict[str, Any]:
    """Lists available backup files for a given server and type.

    This is a read-only operation and does not require a lock. It calls
    :meth:`~.core.bedrock_server.BedrockServer.list_backups`.

    Args:
        server_name (str): The name of the server.
        backup_type (str): The type of backups to list. Valid options are
            "world", "properties", "allowlist", "permissions", or "all"
            (case-insensitive).

    Returns:
        Dict[str, Any]: A dictionary with the operation result.
        On success: ``{"status": "success", "backups": BackupData}``.
        If `backup_type` is specific (e.g., "world"), `BackupData` is ``List[str]``
        of backup file paths.
        If `backup_type` is "all", `BackupData` is ``Dict[str, List[str]]``
        categorizing backups (e.g., ``{"world_backups": [...], "properties_backups": [...]}``).
        An empty list/dict is returned if no backups are found or backup dir is missing.
        On error: ``{"status": "error", "message": "<error_message>"}``.

    Raises:
        InvalidServerNameError: If the server name is empty.
        MissingArgumentError: If `backup_type` is empty.
        UserInputError: If `backup_type` is invalid.
        ConfigurationError: If the server's backup directory is not configured.
        FileOperationError: For OS errors during file listing.
    """
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    try:
        server = app_context.get_server(server_name)
        backup_data = server.list_backups(backup_type)
        return {"status": "success", "backups": backup_data}
    except BSMError as e:
        logger.warning(f"Client error listing backups for server '{server_name}': {e}")
        return {"status": "error", "message": str(e)}
    except Exception as e:
        logger.error(
            f"Unexpected error listing backups for '{server_name}': {e}", exc_info=True
        )
        return {"status": "error", "message": "An unexpected server error occurred."}


@plugin_method("backup_world")
@trigger_plugin_event(before="before_backup", after="after_backup")
def backup_world(
    server_name: str,
    app_context: AppContext,
    stop_start_server: bool = True,
) -> Dict[str, str]:
    """Creates a backup of the server's world directory.

    This operation is thread-safe and guarded by a lock. It calls the internal
    ``_backup_world_data_internal`` method of the
    :class:`~.core.bedrock_server.BedrockServer` instance, which handles
    determining the active world, exporting it to a ``.mcworld`` file, and
    pruning old world backups. If `stop_start_server` is ``True``, the
    :func:`~bedrock_server_manager.api.utils.server_lifecycle_manager`
    is used to manage the server's state.
    Triggers ``before_backup`` and ``after_backup`` plugin events (with type "world").

    Args:
        server_name (str): The name of the server whose world is to be backed up.
        stop_start_server (bool, optional): If ``True``, the server will be
            stopped before the backup and restarted afterwards. Defaults to ``True``.

    Returns:
        Dict[str, str]: A dictionary with the operation result.
        Possible statuses: "success", "error", or "skipped" (if lock not acquired).
        On success: ``{"status": "success", "message": "World backup '<filename>' created..."}``
        On error: ``{"status": "error", "message": "<error_message>"}``.

    Raises:
        MissingArgumentError: If `server_name` is empty.
        BSMError: Propagates errors from underlying operations, including:
            :class:`~.error.ConfigurationError` (backup path not set),
            :class:`~.error.AppFileNotFoundError` (world dir missing),
            :class:`~.error.BackupRestoreError` (export/pruning issues),
            or errors from server stop/start.
    """
    if not _backup_restore_lock.acquire(blocking=False):
        logger.warning(
            f"Backup/restore operation for '{server_name}' is already in progress. Skipping concurrent world backup."
        )
        return {
            "status": "skipped",
            "message": "Backup/restore operation already in progress.",
        }

    try:
        if not server_name:
            raise MissingArgumentError("Server name cannot be empty.")

        logger.info(
            f"API: Initiating world backup for server '{server_name}'. Stop/Start: {stop_start_server}"
        )

        try:
            # Use a context manager to handle stopping and starting the server.
            with server_lifecycle_manager(
                server_name, stop_start_server, app_context=app_context
            ):
                server = app_context.get_server(server_name)
                backup_file = server._backup_world_data_internal()
            return {
                "status": "success",
                "message": f"World backup '{os.path.basename(backup_file)}' created successfully for server '{server_name}'.",
            }

        except BSMError as e:
            logger.error(
                f"API: World backup failed for '{server_name}': {e}", exc_info=True
            )
            return {"status": "error", "message": f"World backup failed: {e}"}
        except Exception as e:
            logger.error(
                f"API: Unexpected error during world backup for '{server_name}': {e}",
                exc_info=True,
            )
            return {
                "status": "error",
                "message": f"Unexpected error during world backup: {e}",
            }

    finally:
        _backup_restore_lock.release()


@plugin_method("backup_config_file")
@trigger_plugin_event(before="before_backup", after="after_backup")
def backup_config_file(
    server_name: str,
    file_to_backup: str,
    app_context: AppContext,
    stop_start_server: bool = True,
) -> Dict[str, str]:
    """Creates a backup of a specific server configuration file.

    This operation is thread-safe and guarded by a lock. It calls the internal
    ``_backup_config_file_internal`` method of the
    :class:`~.core.bedrock_server.BedrockServer` instance. This core method
    copies the specified file (e.g., ``server.properties``) from the server's
    installation directory to a timestamped backup in the server's backup
    directory, then prunes older backups of that file type.
    The :func:`~bedrock_server_manager.api.utils.server_lifecycle_manager`
    is used if `stop_start_server` is ``True``, though typically not strictly
    necessary for config file backups unless there's a concern about live writes.
    Triggers ``before_backup`` and ``after_backup`` plugin events (with type "config_file").

    Args:
        server_name (str): The name of the server.
        file_to_backup (str): The name of the configuration file to back up
            (e.g., "server.properties", "allowlist.json"). This file is expected
            to be in the root of the server's installation directory.
        stop_start_server (bool, optional): If ``True``, the server lifecycle will be
            managed (stopped before, restarted after if it was running). While often
            not strictly needed for config file backups, it can ensure consistency
            if the server might be writing to the file. Defaults to ``True``.

    Returns:
        Dict[str, str]: A dictionary with the operation result.
        Possible statuses: "success", "error", or "skipped" (if lock not acquired).
        On success: ``{"status": "success", "message": "Config file '<name>' backed up as '<backup_name>'..."}``
        If original file not found: ``{"status": "error", "message": "Config file backup failed: File ... not found."}`` (or similar from BSMError)
        On other error: ``{"status": "error", "message": "<error_message>"}``.

    Raises:
        MissingArgumentError: If `server_name` or `file_to_backup` is empty.
        BSMError: Propagates errors from underlying operations, including
            :class:`~.error.ConfigurationError` (backup path not set),
            :class:`~.error.FileOperationError` (file copy/pruning issues),
            or errors from server stop/start if `stop_start_server` is true.
    """
    if not _backup_restore_lock.acquire(blocking=False):
        logger.warning(
            f"Backup/restore operation for '{server_name}' is already in progress. Skipping concurrent config backup."
        )
        return {
            "status": "skipped",
            "message": "Backup/restore operation already in progress.",
        }

    try:
        if not server_name:
            raise MissingArgumentError("Server name cannot be empty.")
        if not file_to_backup:
            raise MissingArgumentError("File to backup cannot be empty.")

        filename_base = os.path.basename(file_to_backup)
        logger.info(
            f"API: Initiating config file backup for '{filename_base}' on server '{server_name}'. Stop/Start: {stop_start_server}"
        )

        try:
            with server_lifecycle_manager(
                server_name, stop_start_server, app_context=app_context
            ):
                server = app_context.get_server(server_name)
                backup_file = server._backup_config_file_internal(filename_base)
            return {
                "status": "success",
                "message": f"Config file '{filename_base}' backed up as '{os.path.basename(backup_file)}' successfully.",
            }

        except (BSMError, FileNotFoundError) as e:
            logger.error(
                f"API: Config file backup failed for '{filename_base}' on '{server_name}': {e}",
                exc_info=True,
            )
            return {"status": "error", "message": f"Config file backup failed: {e}"}
        except Exception as e:
            logger.error(
                f"API: Unexpected error during config file backup for '{server_name}': {e}",
                exc_info=True,
            )
            return {
                "status": "error",
                "message": f"Unexpected error during config file backup: {e}",
            }

    finally:
        _backup_restore_lock.release()


@plugin_method("backup_all")
@trigger_plugin_event(before="before_backup", after="after_backup")
def backup_all(
    server_name: str,
    app_context: AppContext,
    stop_start_server: bool = True,
) -> Dict[str, Any]:
    """Performs a full backup of the server's world and configuration files.

    This operation is thread-safe and guarded by a lock. It calls
    :meth:`~.core.bedrock_server.BedrockServer.backup_all_data`.
    If `stop_start_server` is ``True``, the
    :func:`~bedrock_server_manager.api.utils.server_lifecycle_manager`
    is used to stop the server before the backup. **Note:** The server is
    **not** automatically restarted by this specific API function after the backup,
    even if `stop_start_server` is true; only the stop phase of the lifecycle
    manager is effectively used here for `backup_all`.
    Triggers ``before_backup`` and ``after_backup`` plugin events (with type "all").

    Args:
        server_name (str): The name of the server to back up.
        stop_start_server (bool, optional): If ``True``, the server will be
            stopped before the backup operation begins. Defaults to ``True``.

    Returns:
        Dict[str, Any]: A dictionary with the operation result.
        Possible statuses: "success", "error", or "skipped" (if lock not acquired).
        On success: ``{"status": "success", "message": "Full backup completed...", "details": BackupResultsDict}``
        where ``BackupResultsDict`` maps component names (e.g., "world", "allowlist.json")
        to the path of their backup file, or ``None`` if a component's backup failed.
        On error (e.g., critical world backup failure): ``{"status": "error", "message": "<error_message>"}``.

    Raises:
        MissingArgumentError: If `server_name` is empty.
        BSMError: Propagates errors from underlying operations, including:
            :class:`~.error.ConfigurationError` (backup path not set),
            :class:`~.error.BackupRestoreError` (if critical world backup fails),
            or errors from server stop if `stop_start_server` is true.
    """
    if not _backup_restore_lock.acquire(blocking=False):
        logger.warning(
            f"Backup/restore operation for '{server_name}' is already in progress. Skipping concurrent full backup."
        )
        return {
            "status": "skipped",
            "message": "Backup/restore operation already in progress.",
        }

    try:
        if not server_name:
            raise MissingArgumentError("Server name cannot be empty.")

        logger.info(
            f"API: Initiating full backup for server '{server_name}'. Stop/Start: {stop_start_server}"
        )

        try:
            # The server is stopped before the backup but not restarted after.
            with server_lifecycle_manager(
                server_name, stop_before=stop_start_server, app_context=app_context
            ):
                server = app_context.get_server(server_name)
                backup_results = server.backup_all_data()
            return {
                "status": "success",
                "message": f"Full backup completed successfully for server '{server_name}'.",
                "details": backup_results,
            }

        except BSMError as e:
            logger.error(
                f"API: Full backup failed for '{server_name}': {e}", exc_info=True
            )
            return {"status": "error", "message": f"Full backup failed: {e}"}
        except Exception as e:
            logger.error(
                f"API: Unexpected error during full backup for '{server_name}': {e}",
                exc_info=True,
            )
            return {
                "status": "error",
                "message": f"Unexpected error during full backup: {e}",
            }

    finally:
        _backup_restore_lock.release()


@plugin_method("restore_all")
@trigger_plugin_event(before="before_restore", after="after_restore")
def restore_all(
    server_name: str,
    app_context: AppContext,
    stop_start_server: bool = True,
) -> Dict[str, Any]:
    """Restores the server from the latest available backups.

    This operation is thread-safe and guarded by a lock. It calls
    :meth:`~.core.bedrock_server.BedrockServer.restore_all_data_from_latest`.
    If `stop_start_server` is ``True``, the
    :func:`~bedrock_server_manager.api.utils.server_lifecycle_manager`
    is used to manage the server's state, restarting it only if the restore
    operation (all components) is successful.

    .. warning::
        This operation **OVERWRITES** current world data and configuration files
        in the server's installation directory with content from the latest backups.

    Triggers ``before_restore`` and ``after_restore`` plugin events (with type "all").

    Args:
        server_name (str): The name of the server to restore.
        stop_start_server (bool, optional): If ``True``, the server will be
            stopped before restoring and restarted afterwards only if the entire
            restore operation succeeds. Defaults to ``True``.

    Returns:
        Dict[str, Any]: A dictionary with the operation result.
        Possible statuses: "success", "error", or "skipped" (if lock not acquired).
        On success: ``{"status": "success", "message": "Restore_all completed...", "details": RestoreResultsDict}``
        where ``RestoreResultsDict`` maps component names to their restored paths or ``None`` on failure/skip.
        If no backups found: ``{"status": "success", "message": "No backups found..."}``
        On error: ``{"status": "error", "message": "<error_message>"}`` (e.g., if a component failed to restore).

    Raises:
        MissingArgumentError: If `server_name` is empty.
        BSMError: Propagates errors from underlying operations, including:
            :class:`~.error.ConfigurationError` (backup path not set),
            :class:`~.error.BackupRestoreError` (if any component fails to restore),
            or errors from server stop/start.
    """
    if not _backup_restore_lock.acquire(blocking=False):
        logger.warning(
            f"Backup/restore operation for '{server_name}' is already in progress. Skipping concurrent restore."
        )
        return {
            "status": "skipped",
            "message": "Backup/restore operation already in progress.",
        }

    try:
        if not server_name:
            raise MissingArgumentError("Server name cannot be empty.")

        logger.info(
            f"API: Initiating restore_all for server '{server_name}'. Stop/Start: {stop_start_server}"
        )

        try:
            with server_lifecycle_manager(
                server_name,
                stop_before=stop_start_server,
                restart_on_success_only=True,
                app_context=app_context,
            ):
                server = app_context.get_server(server_name)
                restore_results = server.restore_all_data_from_latest()

            if not restore_results:
                return {
                    "status": "success",
                    "message": f"No backups found for server '{server_name}'. Nothing restored.",
                }
            else:
                return {
                    "status": "success",
                    "message": f"Restore_all completed successfully for server '{server_name}'.",
                    "details": restore_results,
                }

        except BSMError as e:
            logger.error(
                f"API: Restore_all failed for '{server_name}': {e}", exc_info=True
            )
            return {"status": "error", "message": f"Restore_all failed: {e}"}
        except Exception as e:
            logger.error(
                f"API: Unexpected error during restore_all for '{server_name}': {e}",
                exc_info=True,
            )
            return {
                "status": "error",
                "message": f"Unexpected error during restore_all: {e}",
            }

    finally:
        _backup_restore_lock.release()


@plugin_method("restore_world")
@trigger_plugin_event(before="before_restore", after="after_restore")
def restore_world(
    server_name: str,
    backup_file_path: str,
    app_context: AppContext,
    stop_start_server: bool = True,
) -> Dict[str, str]:
    """Restores a server's world from a specific backup file.

    This operation is thread-safe and guarded by a lock. If `stop_start_server`
    is ``True``, it uses the
    :func:`~bedrock_server_manager.api.utils.server_lifecycle_manager`
    to manage the server's state, restarting it only if the restore is successful.
    The core world import is performed by
    :meth:`~.core.bedrock_server.BedrockServer.import_active_world_from_mcworld`.

    .. warning::
        This is a **DESTRUCTIVE** operation. The existing active world directory
        will be deleted before the new world is imported from the backup.

    Triggers ``before_restore`` and ``after_restore`` plugin events (with type "world").

    Args:
        server_name (str): The name of the server.
        backup_file_path (str): The absolute path to the ``.mcworld`` backup file
            to be restored.
        stop_start_server (bool, optional): If ``True``, the server will be
            stopped before restoring and restarted afterwards only if the restore
            is successful. Defaults to ``True``.

    Returns:
        Dict[str, str]: A dictionary with the operation result.
        Possible statuses: "success", "error", or "skipped" (if lock not acquired).
        On success: ``{"status": "success", "message": "World restore from '<filename>' completed..."}``
        On error: ``{"status": "error", "message": "<error_message>"}``.

    Raises:
        MissingArgumentError: If `server_name` or `backup_file_path` is empty.
        AppFileNotFoundError: If `backup_file_path` does not exist.
        BSMError: Propagates errors from underlying operations like
            :class:`~.error.BackupRestoreError`, :class:`~.error.ExtractError`,
            or errors from server stop/start.
    """
    if not _backup_restore_lock.acquire(blocking=False):
        logger.warning(
            f"Backup/restore operation for '{server_name}' is already in progress. Skipping concurrent world restore."
        )
        return {
            "status": "skipped",
            "message": "Backup/restore operation already in progress.",
        }

    try:
        if not server_name:
            raise MissingArgumentError("Server name cannot be empty.")
        if not backup_file_path:
            raise MissingArgumentError("Backup file path cannot be empty.")

        backup_filename = os.path.basename(backup_file_path)
        logger.info(
            f"API: Initiating world restore for '{server_name}' from '{backup_filename}'. Stop/Start: {stop_start_server}"
        )

        try:
            if not os.path.isfile(backup_file_path):
                raise AppFileNotFoundError(backup_file_path, "Backup file")

            with server_lifecycle_manager(
                server_name,
                stop_before=stop_start_server,
                restart_on_success_only=True,
                app_context=app_context,
            ):
                server = app_context.get_server(server_name)
                server.import_active_world_from_mcworld(backup_file_path)

            return {
                "status": "success",
                "message": f"World restore from '{backup_filename}' completed successfully for server '{server_name}'.",
            }

        except (BSMError, FileNotFoundError) as e:
            logger.error(
                f"API: World restore failed for '{server_name}': {e}", exc_info=True
            )
            return {"status": "error", "message": f"World restore failed: {e}"}
        except Exception as e:
            logger.error(
                f"API: Unexpected error during world restore for '{server_name}': {e}",
                exc_info=True,
            )
            return {
                "status": "error",
                "message": f"Unexpected error during world restore: {e}",
            }

    finally:
        _backup_restore_lock.release()


@plugin_method("restore_config_file")
@trigger_plugin_event(before="before_restore", after="after_restore")
def restore_config_file(
    server_name: str,
    backup_file_path: str,
    app_context: AppContext,
    stop_start_server: bool = True,
) -> Dict[str, str]:
    """Restores a specific config file from a backup.

    This operation is thread-safe and guarded by a lock. If `stop_start_server`
    is ``True``, it uses the
    :func:`~bedrock_server_manager.api.utils.server_lifecycle_manager`
    to manage the server's state, restarting it only if the restore is successful.
    The core config file restoration is performed by the internal
    ``_restore_config_file_internal`` method of the
    :class:`~.core.bedrock_server.BedrockServer` instance.

    .. warning::
        This operation **OVERWRITES** the current version of the configuration
        file in the server's installation directory with the content from the backup.

    Triggers ``before_restore`` and ``after_restore`` plugin events (with type "config_file").

    Args:
        server_name (str): The name of the server.
        backup_file_path (str): The absolute path to the configuration backup file
            (e.g., ``.../server_backup_YYYYMMDD_HHMMSS.properties``).
        stop_start_server (bool, optional): If ``True``, the server will be
            stopped before restoring and restarted afterwards only if the restore
            is successful. Defaults to ``True``.

    Returns:
        Dict[str, str]: A dictionary with the operation result.
        Possible statuses: "success", "error", or "skipped" (if lock not acquired).
        On success: ``{"status": "success", "message": "Config file '<original_name>' restored from '<backup_name>'..."}``
        On error: ``{"status": "error", "message": "<error_message>"}``.

    Raises:
        MissingArgumentError: If `server_name` or `backup_file_path` is empty.
        AppFileNotFoundError: If `backup_file_path` does not exist.
        UserInputError: If the backup filename format is unrecognized.
        BSMError: Propagates errors from underlying operations like
            :class:`~.error.FileOperationError` or errors from server stop/start.
    """
    if not _backup_restore_lock.acquire(blocking=False):
        logger.warning(
            f"Backup/restore operation for '{server_name}' is already in progress. Skipping concurrent config restore."
        )
        return {
            "status": "skipped",
            "message": "Backup/restore operation already in progress.",
        }

    try:
        if not server_name:
            raise MissingArgumentError("Server name cannot be empty.")
        if not backup_file_path:
            raise MissingArgumentError("Backup file path cannot be empty.")

        backup_filename = os.path.basename(backup_file_path)
        logger.info(
            f"API: Initiating config restore for '{server_name}' from '{backup_filename}'. Stop/Start: {stop_start_server}"
        )

        try:
            if not os.path.isfile(backup_file_path):
                raise AppFileNotFoundError(backup_file_path, "Backup file")

            with server_lifecycle_manager(
                server_name,
                stop_before=stop_start_server,
                restart_on_success_only=True,
                app_context=app_context,
            ):
                server = app_context.get_server(server_name)
                restored_file = server._restore_config_file_internal(backup_file_path)

            return {
                "status": "success",
                "message": f"Config file '{os.path.basename(restored_file)}' restored successfully from '{backup_filename}'.",
            }

        except (BSMError, FileNotFoundError) as e:
            logger.error(
                f"API: Config file restore failed for '{server_name}': {e}",
                exc_info=True,
            )
            return {"status": "error", "message": f"Config file restore failed: {e}"}
        except Exception as e:
            logger.error(
                f"API: Unexpected error during config file restore for '{server_name}': {e}",
                exc_info=True,
            )
            return {
                "status": "error",
                "message": f"Unexpected error during config file restore: {e}",
            }

    finally:
        _backup_restore_lock.release()


@plugin_method("prune_old_backups")
@trigger_plugin_event(before="before_prune_backups", after="after_prune_backups")
def prune_old_backups(server_name: str, app_context: AppContext) -> Dict[str, str]:
    """Prunes old backups for a server based on retention settings.

    This operation is thread-safe and guarded by a lock. It iteratively calls
    :meth:`~.core.bedrock_server.BedrockServer.prune_server_backups`
    for the server's world (``.mcworld`` files) and standard configuration
    files (``server.properties``, ``allowlist.json``, ``permissions.json``).
    The number of backups to keep is determined by the ``retention.backups``
    application setting.
    Triggers ``before_prune_backups`` and ``after_prune_backups`` plugin events.

    Args:
        server_name (str): The name of the server whose backups are to be pruned.

    Returns:
        Dict[str, str]: A dictionary with the operation result.
        Possible statuses: "success", "error", or "skipped" (if lock not acquired).
        On full success: ``{"status": "success", "message": "Backup pruning completed..."}``
        If some components fail pruning: ``{"status": "error", "message": "Pruning completed with errors: <details>"}``
        If backup directory not found: ``{"status": "success", "message": "No backup directory found..."}``
        On other setup error: ``{"status": "error", "message": "<error_message>"}``.

    Raises:
        MissingArgumentError: If `server_name` is empty.
        BSMError: Propagates errors from underlying operations, particularly
            :class:`~.error.ConfigurationError` if backup path is not set,
            or :class:`~.error.UserInputError` if retention settings are invalid.
            Individual :class:`~.error.FileOperationError` for components are
            typically aggregated into the error message.
    """
    if not _backup_restore_lock.acquire(blocking=False):
        logger.warning(
            f"Backup/restore operation for '{server_name}' is already in progress. Skipping concurrent prune."
        )
        return {
            "status": "skipped",
            "message": "Backup/restore operation already in progress.",
        }

    try:
        if not server_name:
            raise MissingArgumentError("Server name cannot be empty.")

        logger.info(
            f"API: Initiating pruning of old backups for server '{server_name}'."
        )

        try:
            server = app_context.get_server(server_name)
            # If the backup directory doesn't exist, there's nothing to do.
            if not server.server_backup_directory or not os.path.isdir(
                server.server_backup_directory
            ):
                return {
                    "status": "success",
                    "message": "No backup directory found, nothing to prune.",
                }

            pruning_errors = []
            # Prune world backups.
            try:
                world_name = server.get_world_name()
                world_name_prefix = f"{world_name}_backup_"
                server.prune_server_backups(world_name_prefix, "mcworld")
            except Exception as e:
                err_msg = f"world backups ({type(e).__name__})"
                pruning_errors.append(err_msg)
                logger.error(
                    f"Error pruning world backups for '{server_name}': {e}",
                    exc_info=True,
                )

            # Define config files and their corresponding prefixes/extensions to prune.
            config_file_types = {
                "server.properties_backup_": "properties",
                "allowlist_backup_": "json",
                "permissions_backup_": "json",
            }
            # Prune each type of config file backup.
            for prefix, ext in config_file_types.items():
                try:
                    server.prune_server_backups(prefix, ext)
                except Exception as e:
                    err_msg = f"config backups ({prefix}*.{ext}) ({type(e).__name__})"
                    pruning_errors.append(err_msg)
                    logger.error(
                        f"Error pruning {prefix}*.{ext} for '{server_name}': {e}",
                        exc_info=True,
                    )

            # Report final status based on whether any errors occurred.
            if pruning_errors:
                return {
                    "status": "error",
                    "message": f"Pruning completed with errors: {'; '.join(pruning_errors)}",
                }
            else:
                return {
                    "status": "success",
                    "message": f"Backup pruning completed for server '{server_name}'.",
                }

        except (BSMError, ValueError) as e:
            logger.error(
                f"API: Cannot prune backups for '{server_name}': {e}", exc_info=True
            )
            return {"status": "error", "message": f"Pruning setup error: {e}"}
        except Exception as e:
            logger.error(
                f"API: Unexpected error during backup pruning for '{server_name}': {e}",
                exc_info=True,
            )
            return {
                "status": "error",
                "message": f"Unexpected error during pruning: {e}",
            }

    finally:
        _backup_restore_lock.release()
