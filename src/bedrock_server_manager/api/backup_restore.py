# bedrock_server_manager/api/backup_restore.py
"""Provides API functions for server backup, restore, and pruning operations.

This module offers a high-level interface for managing the backup and restoration
of Bedrock server data. It orchestrates calls to methods of the
:class:`~bedrock_server_manager.core.bedrock_server.BedrockServer` class,
primarily those provided by the
:class:`~bedrock_server_manager.core.server.backup_restore.ServerBackups`.

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

import aiofiles.ospath

from ..context import AppContext
from ..error import (
    AppFileNotFoundError,
    BSMError,
    IncompleteOperationError,
)
from ..failures import classify_failure
from ..logging import log_operation_error
from ..plugins.api_bridge import api_method
from ..plugins.event_trigger import trigger_event
from ..plugins.runtime_capabilities import server_lifecycle_manager
from ..results import CleanupResult
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
    try:
        server = app_context.get_server(server_name, require_installation=False)
        backup_data = await server.backups.list_backups(backup_type)
        return ListBackupFilesResponse.model_validate(
            {"status": "success", "backups": backup_data}
        )
    except BSMError as e:
        logger.warning(
            "Client error listing backups for server '%s': %s", server_name, e
        )
        raise
    except Exception as e:
        log_operation_error(
            logger,
            "Unexpected error listing backups for '%s': %s",
            server_name,
            e,
            error=e,
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
    server = app_context.get_server(server_name)
    try:
        await server.operation_lock.acquire(timeout=300)
    except asyncio.TimeoutError:
        logger.warning(
            "An operation for '%s' is already in progress. Skipping concurrent world backup.",
            server_name,
        )
        return BackupWorldResponse(
            server_name=server_name,
            status="skipped",
            message="Backup/restore operation already in progress.",
        )
    try:
        logger.debug("Initiating world backup for server '%s'.", server_name)
        try:
            backup_file = await server.backups.backup_world()
            return BackupWorldResponse(
                server_name=server_name,
                status="success",
                message=f"World backup '{os.path.basename(str(backup_file))}' created successfully for server '{server_name}'.",
            )
        except BSMError as e:
            log_operation_error(
                logger, "World backup failed for '%s': %s", server_name, e, error=e
            )
            raise
        except Exception as e:
            log_operation_error(
                logger,
                "Unexpected error during world backup for '%s': %s",
                server_name,
                e,
                error=e,
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
    server = app_context.get_server(server_name)
    try:
        await server.operation_lock.acquire(timeout=300)
    except asyncio.TimeoutError:
        logger.warning(
            "An operation for '%s' is already in progress. Skipping concurrent config backup.",
            server_name,
        )
        return BackupConfigFileResponse(
            server_name=server_name,
            status="skipped",
            message="Backup/restore operation already in progress.",
        )
    try:
        filename_base = os.path.basename(file_to_backup)
        logger.debug(
            "Initiating config file backup for '%s' on server '%s'.",
            filename_base,
            server_name,
        )
        try:
            backup_file = await server.backups.backup_config(filename_base)
            if backup_file is None:
                raise AppFileNotFoundError(filename_base, "Server configuration file")
            return BackupConfigFileResponse(
                server_name=server_name,
                status="success",
                message=f"Config file '{filename_base}' backed up as '{os.path.basename(str(backup_file))}' successfully.",
            )
        except (BSMError, FileNotFoundError) as e:
            log_operation_error(
                logger,
                "Config file backup failed for '%s' on '%s': %s",
                filename_base,
                server_name,
                e,
                error=e,
            )
            raise
        except Exception as e:
            log_operation_error(
                logger,
                "Unexpected error during config file backup for '%s': %s",
                server_name,
                e,
                error=e,
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
    server = app_context.get_server(server_name)
    try:
        await server.operation_lock.acquire(timeout=300)
    except asyncio.TimeoutError:
        logger.warning(
            "An operation for '%s' is already in progress. Skipping concurrent full backup.",
            server_name,
        )
        return BackupAllResponse(
            server_name=server_name,
            status="skipped",
            message="Backup/restore operation already in progress.",
        )
    try:
        logger.debug("Initiating full backup for server '%s'.", server_name)
        try:
            backup_results = await server.backups.backup_all_data()
            return BackupAllResponse(
                server_name=server_name,
                status="partial" if backup_results.outcome == "partial" else "success",
                message=f"Backup for '{server_name}' {backup_results.outcome}.",
                details=backup_results,
            )
        except BSMError as e:
            log_operation_error(
                logger, "Full backup failed for '%s': %s", server_name, e, error=e
            )
            raise
        except Exception as e:
            log_operation_error(
                logger,
                "Unexpected error during full backup for '%s': %s",
                server_name,
                e,
                error=e,
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
    server = app_context.get_server(server_name, require_installation=False)
    try:
        await server.operation_lock.acquire(timeout=300)
    except asyncio.TimeoutError:
        logger.warning(
            "An operation for '%s' is already in progress. Skipping concurrent restore.",
            server_name,
        )
        return RestoreAllResponse(
            server_name=server_name,
            status="skipped",
            message="Backup/restore operation already in progress.",
        )
    try:
        logger.debug(
            "Initiating restore_all for server '%s'. Stop/Start: %s",
            server_name,
            stop_start_server,
        )
        try:
            async with server_lifecycle_manager(
                server_name,
                stop_before=stop_start_server,
                restart_on_success_only=True,
                app_context=app_context,
            ):
                restore_results = await server.backups.restore_all_data_from_latest()
            return RestoreAllResponse(
                server_name=server_name,
                status="skipped" if restore_results.outcome == "noop" else "success",
                message=f"Restore for '{server_name}' {restore_results.outcome}.",
                details=restore_results,
            )
        except BSMError as e:
            log_operation_error(
                logger, "Restore_all failed for '%s': %s", server_name, e, error=e
            )
            raise
        except Exception as e:
            log_operation_error(
                logger,
                "Unexpected error during restore_all for '%s': %s",
                server_name,
                e,
                error=e,
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
    server = app_context.get_server(server_name, require_installation=False)
    try:
        await server.operation_lock.acquire(timeout=300)
    except asyncio.TimeoutError:
        logger.warning(
            "An operation for '%s' is already in progress. Skipping concurrent world restore.",
            server_name,
        )
        return RestoreWorldResponse(
            server_name=server_name,
            status="skipped",
            message="Backup/restore operation already in progress.",
        )
    try:
        backup_filename = os.path.basename(backup_file_path)
        logger.debug(
            "Initiating world restore for '%s' from '%s'. Stop/Start: %s",
            server_name,
            backup_filename,
            stop_start_server,
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
                await server.worlds.import_world(backup_file_path)
            return RestoreWorldResponse(
                server_name=server_name,
                status="success",
                message=f"World restore from '{backup_filename}' completed successfully for server '{server_name}'.",
            )
        except (BSMError, FileNotFoundError) as e:
            log_operation_error(
                logger, "World restore failed for '%s': %s", server_name, e, error=e
            )
            raise
        except Exception as e:
            log_operation_error(
                logger,
                "Unexpected error during world restore for '%s': %s",
                server_name,
                e,
                error=e,
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
    server = app_context.get_server(server_name, require_installation=False)
    try:
        await server.operation_lock.acquire(timeout=300)
    except asyncio.TimeoutError:
        logger.warning(
            "An operation for '%s' is already in progress. Skipping concurrent config restore.",
            server_name,
        )
        return RestoreConfigFileResponse(
            server_name=server_name,
            status="skipped",
            message="Backup/restore operation already in progress.",
        )
    try:
        backup_filename = os.path.basename(backup_file_path)
        logger.debug(
            "Initiating config restore for '%s' from '%s'. Stop/Start: %s",
            server_name,
            backup_filename,
            stop_start_server,
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
                restored_file = await server.backups.restore_config(backup_file_path)
            return RestoreConfigFileResponse(
                server_name=server_name,
                status="success",
                message=f"Config file '{os.path.basename(str(restored_file))}' restored successfully from '{backup_filename}'.",
            )
        except (BSMError, FileNotFoundError) as e:
            log_operation_error(
                logger,
                "Config file restore failed for '%s': %s",
                server_name,
                e,
                error=e,
            )
            raise
        except Exception as e:
            log_operation_error(
                logger,
                "Unexpected error during config file restore for '%s': %s",
                server_name,
                e,
                error=e,
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
    server = app_context.get_server(server_name, require_installation=False)
    try:
        await server.operation_lock.acquire(timeout=300)
    except asyncio.TimeoutError:
        logger.warning(
            "An operation for '%s' is already in progress. Skipping concurrent prune.",
            server_name,
        )
        return PruneOldBackupsResponse(
            server_name=server_name,
            status="skipped",
            message="Backup/restore operation already in progress.",
        )
    try:
        if (
            not server.backups.server_backup_directory
            or not await aiofiles.ospath.isdir(server.backups.server_backup_directory)
        ):
            return PruneOldBackupsResponse(
                server_name=server_name,
                status="skipped",
                message="No backup directory is available.",
            )
        results = []
        world = await server.get_world_name()
        selections = [
            (server.backups._world_prefix(world), "mcworld"),
            ("server_backup_", "properties"),
            ("allowlist_backup_", "json"),
            ("permissions_backup_", "json"),
        ]
        for prefix, extension in selections:
            try:
                results.append(
                    await server.backups.prune_server_backups(prefix, extension)
                )
            except Exception as error:
                results.append(
                    CleanupResult(failures={prefix: classify_failure(error).error})
                )
        result = CleanupResult(
            deleted=[path for item in results for path in item.deleted],
            retained=[path for item in results for path in item.retained],
            failures={
                path: error for item in results for path, error in item.failures.items()
            },
        )
        if result.outcome == "failed":
            raise IncompleteOperationError("Backup retention failed.", result)
        return PruneOldBackupsResponse(
            server_name=server_name,
            status=(
                "partial"
                if result.failures
                else "skipped" if result.outcome == "noop" else "success"
            ),
            message=f"Backup retention {result.outcome}: {len(result.deleted)} deleted, {len(result.failures)} failed.",
            result=result,
        )
    finally:
        server.operation_lock.release()
