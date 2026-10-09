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

Operations involving file modifications are thread-safe using a per-server operation lock
(``server.operation_lock``). For actions requiring the server to be offline,
this module utilizes the
:func:`~bedrock_server_manager.api.server.server_lifecycle_manager`
to safely stop and restart the server. All functions are exposed to the plugin system.
"""

import asyncio
import logging
import os

from ..context import AppContext
from ..error import (
    AppFileNotFoundError,
    BSMError,
    InvalidServerNameError,
    MissingArgumentError,
)
from ..plugins.api_bridge import api_method
from ..plugins.event_trigger import trigger_event
from ..plugins.runtime_capabilities import server_lifecycle_manager
from .models.backup_restore import (
    BackupAllRequest,
    BackupAllResponse,
    BackupConfigFileRequest,
    BackupConfigFileResponse,
    BackupWorldRequest,
    BackupWorldResponse,
    ListBackupFilesRequest,
    ListBackupFilesResponse,
    PruneOldBackupsRequest,
    PruneOldBackupsResponse,
    RestoreAllRequest,
    RestoreAllResponse,
    RestoreConfigFileRequest,
    RestoreConfigFileResponse,
    RestoreWorldRequest,
    RestoreWorldResponse,
)

logger = logging.getLogger(__name__)


@api_method("list_backup_files")
async def list_backup_files(
    request: ListBackupFilesRequest, *, app_context: AppContext
) -> ListBackupFilesResponse:
    """Lists available backup files for a given server and type.

    Accepts ListBackupFilesRequest and returns ListBackupFilesResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    server_name = request.server_name
    backup_type = request.backup_type
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    try:
        server = app_context.get_server(server_name)
        backup_data = await server.list_backups(backup_type)
        return ListBackupFilesResponse.model_validate(
            {"status": "success", "backups": backup_data}
        )
    except BSMError as e:
        logger.warning(f"Client error listing backups for server '{server_name}': {e}")
        raise
    except Exception as e:
        logger.error(
            f"Unexpected error listing backups for '{server_name}': {e}", exc_info=True
        )
        raise


@api_method("backup_world")
@trigger_event(
    before="before_backup",
    after="after_backup",
    identity_keys=("server_name",),
)
async def backup_world(
    request: BackupWorldRequest, *, app_context: AppContext
) -> BackupWorldResponse:
    """Creates a backup of the server's world directory.

    Accepts BackupWorldRequest and returns BackupWorldResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    server_name = request.server_name
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    server = app_context.get_server(server_name)
    try:
        await server.operation_lock.acquire(timeout=300)
    except asyncio.TimeoutError:
        logger.warning(
            f"An operation for '{server_name}' is already in progress. Skipping concurrent world backup."
        )
        return BackupWorldResponse.model_validate(
            {
                "status": "skipped",
                "message": "Backup/restore operation already in progress.",
            }
        )
    try:
        logger.info(f"API: Initiating world backup for server '{server_name}'.")
        try:
            backup_file = await server._backup_world_data_internal()
            return BackupWorldResponse.model_validate(
                {
                    "status": "success",
                    "message": f"World backup '{os.path.basename(str(backup_file))}' created successfully for server '{server_name}'.",
                }
            )
        except BSMError as e:
            logger.error(
                f"API: World backup failed for '{server_name}': {e}", exc_info=True
            )
            raise
        except Exception as e:
            logger.error(
                f"API: Unexpected error during world backup for '{server_name}': {e}",
                exc_info=True,
            )
            raise
    finally:
        server.operation_lock.release()


@api_method("backup_config_file")
@trigger_event(
    before="before_backup",
    after="after_backup",
    identity_keys=("server_name",),
)
async def backup_config_file(
    request: BackupConfigFileRequest, *, app_context: AppContext
) -> BackupConfigFileResponse:
    """Creates a backup of a specific server configuration file.

    Accepts BackupConfigFileRequest and returns BackupConfigFileResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    server_name = request.server_name
    file_to_backup = request.file_to_backup
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    if not file_to_backup:
        raise MissingArgumentError("File to backup cannot be empty.")
    server = app_context.get_server(server_name)
    try:
        await server.operation_lock.acquire(timeout=300)
    except asyncio.TimeoutError:
        logger.warning(
            f"An operation for '{server_name}' is already in progress. Skipping concurrent config backup."
        )
        return BackupConfigFileResponse.model_validate(
            {
                "status": "skipped",
                "message": "Backup/restore operation already in progress.",
            }
        )
    try:
        filename_base = os.path.basename(file_to_backup)
        logger.info(
            f"API: Initiating config file backup for '{filename_base}' on server '{server_name}'."
        )
        try:
            backup_file = await server._backup_config_file_internal(filename_base)
            return BackupConfigFileResponse.model_validate(
                {
                    "status": "success",
                    "message": f"Config file '{filename_base}' backed up as '{os.path.basename(str(backup_file))}' successfully.",
                }
            )
        except (BSMError, FileNotFoundError) as e:
            logger.error(
                f"API: Config file backup failed for '{filename_base}' on '{server_name}': {e}",
                exc_info=True,
            )
            raise
        except Exception as e:
            logger.error(
                f"API: Unexpected error during config file backup for '{server_name}': {e}",
                exc_info=True,
            )
            raise
    finally:
        server.operation_lock.release()


@api_method("backup_all")
@trigger_event(
    before="before_backup",
    after="after_backup",
    identity_keys=("server_name",),
)
async def backup_all(
    request: BackupAllRequest, *, app_context: AppContext
) -> BackupAllResponse:
    """Performs a full backup of the server's world and configuration files.

    Accepts BackupAllRequest and returns BackupAllResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    server_name = request.server_name
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    server = app_context.get_server(server_name)
    try:
        await server.operation_lock.acquire(timeout=300)
    except asyncio.TimeoutError:
        logger.warning(
            f"An operation for '{server_name}' is already in progress. Skipping concurrent full backup."
        )
        return BackupAllResponse.model_validate(
            {
                "status": "skipped",
                "message": "Backup/restore operation already in progress.",
            }
        )
    try:
        logger.info(f"API: Initiating full backup for server '{server_name}'.")
        try:
            backup_results = await server.backup_all_data()
            return BackupAllResponse.model_validate(
                {
                    "status": "success",
                    "message": f"Full backup completed successfully for server '{server_name}'.",
                    "details": backup_results,
                }
            )
        except BSMError as e:
            logger.error(
                f"API: Full backup failed for '{server_name}': {e}", exc_info=True
            )
            raise
        except Exception as e:
            logger.error(
                f"API: Unexpected error during full backup for '{server_name}': {e}",
                exc_info=True,
            )
            raise
    finally:
        server.operation_lock.release()


@api_method("restore_all")
@trigger_event(
    before="before_restore",
    after="after_restore",
    identity_keys=("server_name",),
)
async def restore_all(
    request: RestoreAllRequest, *, app_context: AppContext
) -> RestoreAllResponse:
    """Restores the server from the latest available backups.

    Accepts RestoreAllRequest and returns RestoreAllResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    server_name = request.server_name
    stop_start_server = request.stop_start_server
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    server = app_context.get_server(server_name)
    try:
        await server.operation_lock.acquire(timeout=300)
    except asyncio.TimeoutError:
        logger.warning(
            f"An operation for '{server_name}' is already in progress. Skipping concurrent restore."
        )
        return RestoreAllResponse.model_validate(
            {
                "status": "skipped",
                "message": "Backup/restore operation already in progress.",
            }
        )
    try:
        logger.info(
            f"API: Initiating restore_all for server '{server_name}'. Stop/Start: {stop_start_server}"
        )
        try:
            async with server_lifecycle_manager(
                server_name,
                stop_before=stop_start_server,
                restart_on_success_only=True,
                app_context=app_context,
            ):
                restore_results = await server.restore_all_data_from_latest()
            if not restore_results:
                return RestoreAllResponse.model_validate(
                    {
                        "status": "success",
                        "message": f"No backups found for server '{server_name}'. Nothing restored.",
                    }
                )
            else:
                return RestoreAllResponse.model_validate(
                    {
                        "status": "success",
                        "message": f"Restore_all completed successfully for server '{server_name}'.",
                        "details": restore_results,
                    }
                )
        except BSMError as e:
            logger.error(
                f"API: Restore_all failed for '{server_name}': {e}", exc_info=True
            )
            raise
        except Exception as e:
            logger.error(
                f"API: Unexpected error during restore_all for '{server_name}': {e}",
                exc_info=True,
            )
            raise
    finally:
        server.operation_lock.release()


@api_method("restore_world")
@trigger_event(
    before="before_restore",
    after="after_restore",
    identity_keys=("server_name",),
)
async def restore_world(
    request: RestoreWorldRequest, *, app_context: AppContext
) -> RestoreWorldResponse:
    """Restores a server's world from a specific backup file.

    Accepts RestoreWorldRequest and returns RestoreWorldResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    server_name = request.server_name
    backup_file_path = request.backup_file_path
    stop_start_server = request.stop_start_server
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    if not backup_file_path:
        raise MissingArgumentError("Backup file path cannot be empty.")
    server = app_context.get_server(server_name)
    try:
        await server.operation_lock.acquire(timeout=300)
    except asyncio.TimeoutError:
        logger.warning(
            f"An operation for '{server_name}' is already in progress. Skipping concurrent world restore."
        )
        return RestoreWorldResponse.model_validate(
            {
                "status": "skipped",
                "message": "Backup/restore operation already in progress.",
            }
        )
    try:
        backup_filename = os.path.basename(backup_file_path)
        logger.info(
            f"API: Initiating world restore for '{server_name}' from '{backup_filename}'. Stop/Start: {stop_start_server}"
        )
        try:
            if not os.path.isfile(backup_file_path):
                raise AppFileNotFoundError(backup_file_path, "Backup file")
            async with server_lifecycle_manager(
                server_name,
                stop_before=stop_start_server,
                restart_on_success_only=True,
                app_context=app_context,
            ):
                await server.import_world(backup_file_path)
            return RestoreWorldResponse.model_validate(
                {
                    "status": "success",
                    "message": f"World restore from '{backup_filename}' completed successfully for server '{server_name}'.",
                }
            )
        except (BSMError, FileNotFoundError) as e:
            logger.error(
                f"API: World restore failed for '{server_name}': {e}", exc_info=True
            )
            raise
        except Exception as e:
            logger.error(
                f"API: Unexpected error during world restore for '{server_name}': {e}",
                exc_info=True,
            )
            raise
    finally:
        server.operation_lock.release()


@api_method("restore_config_file")
@trigger_event(
    before="before_restore",
    after="after_restore",
    identity_keys=("server_name",),
)
async def restore_config_file(
    request: RestoreConfigFileRequest, *, app_context: AppContext
) -> RestoreConfigFileResponse:
    """Restores a specific config file from a backup.

    Accepts RestoreConfigFileRequest and returns RestoreConfigFileResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    server_name = request.server_name
    backup_file_path = request.backup_file_path
    stop_start_server = request.stop_start_server
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    if not backup_file_path:
        raise MissingArgumentError("Backup file path cannot be empty.")
    server = app_context.get_server(server_name)
    try:
        await server.operation_lock.acquire(timeout=300)
    except asyncio.TimeoutError:
        logger.warning(
            f"An operation for '{server_name}' is already in progress. Skipping concurrent config restore."
        )
        return RestoreConfigFileResponse.model_validate(
            {
                "status": "skipped",
                "message": "Backup/restore operation already in progress.",
            }
        )
    try:
        backup_filename = os.path.basename(backup_file_path)
        logger.info(
            f"API: Initiating config restore for '{server_name}' from '{backup_filename}'. Stop/Start: {stop_start_server}"
        )
        try:
            if not os.path.isfile(backup_file_path):
                raise AppFileNotFoundError(backup_file_path, "Backup file")
            async with server_lifecycle_manager(
                server_name,
                stop_before=stop_start_server,
                restart_on_success_only=True,
                app_context=app_context,
            ):
                restored_file = await server._restore_config_file_internal(
                    backup_file_path
                )
            return RestoreConfigFileResponse.model_validate(
                {
                    "status": "success",
                    "message": f"Config file '{os.path.basename(str(restored_file))}' restored successfully from '{backup_filename}'.",
                }
            )
        except (BSMError, FileNotFoundError) as e:
            logger.error(
                f"API: Config file restore failed for '{server_name}': {e}",
                exc_info=True,
            )
            raise
        except Exception as e:
            logger.error(
                f"API: Unexpected error during config file restore for '{server_name}': {e}",
                exc_info=True,
            )
            raise
    finally:
        server.operation_lock.release()


@api_method("prune_old_backups")
@trigger_event(
    before="before_prune_backups",
    after="after_prune_backups",
    identity_keys=("server_name",),
)
async def prune_old_backups(
    request: PruneOldBackupsRequest, *, app_context: AppContext
) -> PruneOldBackupsResponse:
    """Prunes old backups for a server based on retention settings.

    Accepts PruneOldBackupsRequest and returns PruneOldBackupsResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    server_name = request.server_name
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    server = app_context.get_server(server_name)
    try:
        await server.operation_lock.acquire(timeout=300)
    except asyncio.TimeoutError:
        logger.warning(
            f"An operation for '{server_name}' is already in progress. Skipping concurrent prune."
        )
        return PruneOldBackupsResponse.model_validate(
            {
                "status": "skipped",
                "message": "Backup/restore operation already in progress.",
            }
        )
    try:
        logger.info(
            f"API: Initiating pruning of old backups for server '{server_name}'."
        )
        try:
            if not server.server_backup_directory or not os.path.isdir(
                server.server_backup_directory
            ):
                return PruneOldBackupsResponse.model_validate(
                    {
                        "status": "success",
                        "message": "No backup directory found, nothing to prune.",
                    }
                )
            pruning_errors = []
            try:
                world_name = await server.get_world_name()
                world_name_prefix = f"{world_name}_backup_"
                await server.prune_server_backups(world_name_prefix, "mcworld")
            except Exception as e:
                err_msg = f"world backups ({type(e).__name__})"
                pruning_errors.append(err_msg)
                logger.error(
                    f"Error pruning world backups for '{server_name}': {e}",
                    exc_info=True,
                )
            config_file_types = {
                "server.properties_backup_": "properties",
                "allowlist_backup_": "json",
                "permissions_backup_": "json",
            }
            for prefix, ext in config_file_types.items():
                try:
                    await server.prune_server_backups(prefix, ext)
                except Exception as e:
                    err_msg = f"config backups ({prefix}*.{ext}) ({type(e).__name__})"
                    pruning_errors.append(err_msg)
                    logger.error(
                        f"Error pruning {prefix}*.{ext} for '{server_name}': {e}",
                        exc_info=True,
                    )
            if pruning_errors:
                raise BSMError(
                    f"Pruning completed with errors: {'; '.join(pruning_errors)}"
                )
            else:
                return PruneOldBackupsResponse.model_validate(
                    {
                        "status": "success",
                        "message": f"Backup pruning completed for server '{server_name}'.",
                    }
                )
        except (BSMError, ValueError) as e:
            logger.error(
                f"API: Cannot prune backups for '{server_name}': {e}", exc_info=True
            )
            raise
        except Exception as e:
            logger.error(
                f"API: Unexpected error during backup pruning for '{server_name}': {e}",
                exc_info=True,
            )
            raise
    finally:
        server.operation_lock.release()
