# bedrock_server_manager/api/backup_restore.py
"""Provide API functions for server backup, restore, and pruning operations."""

import asyncio
import logging
import os
from typing import Literal

import aiofiles.ospath

from ..context import AppContext
from ..error import (
    AppFileNotFoundError,
    BackupRestoreError,
    BSMError,
    IncompleteOperationError,
)
from ..events import trigger_event
from ..events.operations import OperationName, track_operation
from ..logging import log_operation_error
from ..plugins.api_bridge import api_method
from .models.backup_restore import (
    BackupAllRequest,
    BackupAllResponse,
    BackupConfigFileRequest,
    BackupConfigFileResponse,
    BackupHealthResponse,
    BackupWorldRequest,
    BackupWorldResponse,
    CleanupBackupDestinationRequest,
    CleanupBackupDestinationResponse,
    CreateSnapshotRequest,
    CreateSnapshotResponse,
    InspectSnapshotRequest,
    InspectSnapshotResponse,
    ListBackupFilesRequest,
    ListBackupFilesResponse,
    ListSnapshotsRequest,
    ListSnapshotsResponse,
    ManageSnapshotRequest,
    ManageSnapshotResponse,
    PlanSnapshotRestoreRequest,
    PlanSnapshotRestoreResponse,
    PrepareBackupCopyRequest,
    PrepareBackupCopyResponse,
    PruneOldBackupsRequest,
    PruneOldBackupsResponse,
    RecoveryReportResponse,
    RestoreAllRequest,
    RestoreAllResponse,
    RestoreConfigFileRequest,
    RestoreConfigFileResponse,
    RestoreRecoveryResponse,
    RestoreSnapshotRequest,
    RestoreSnapshotResponse,
    RestoreWorldRequest,
    RestoreWorldResponse,
    SnapshotReuseRequest,
    SnapshotReuseResponse,
)
from .server import server_lifecycle_manager

logger = logging.getLogger(__name__)


@api_method("list_backup_files")
async def list_backup_files(
    request: ListBackupFilesRequest, *, app_context: AppContext
) -> ListBackupFilesResponse:
    """Lists available backup files for a given server and type."""
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
@track_operation(OperationName.BACKUP_REQUEST)
@trigger_event(
    before="before_backup",
    after="after_backup",
    identity_keys=("server_name",),
)
async def backup_world(
    request: BackupWorldRequest, *, app_context: AppContext
) -> BackupWorldResponse:
    """Create a backup of the server's world directory."""
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
@track_operation(OperationName.BACKUP_REQUEST)
@trigger_event(
    before="before_backup",
    after="after_backup",
    identity_keys=("server_name",),
)
async def backup_config_file(
    request: BackupConfigFileRequest, *, app_context: AppContext
) -> BackupConfigFileResponse:
    """Create a backup of a specific server configuration file."""
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
@track_operation(OperationName.BACKUP_REQUEST)
@trigger_event(
    before="before_backup",
    after="after_backup",
    identity_keys=("server_name",),
)
async def backup_all(
    request: BackupAllRequest, *, app_context: AppContext
) -> BackupAllResponse:
    """Performs a full backup of the server's world and configuration files."""
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
        logger.debug(
            "Initiating backup with requested content selection for server '%s'.",
            server_name,
        )
        try:
            sequence = app_context.operations.sequence()
            names = {item.name for item in sequence.ancestry} if sequence else set()
            purpose: Literal["manual", "pre_start", "pre_update"] = (
                "pre_update"
                if OperationName.SERVER_UPDATE in names
                else "pre_start" if OperationName.SERVER_START in names else "manual"
            )
            backup_results = await server.backups.backup_all_data(
                purpose=purpose,
                mode=request.mode,
                components=request.components,
                encrypted=request.encrypted,
            )
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
@track_operation(OperationName.BACKUP_RESTORE)
@trigger_event(
    before="before_restore",
    after="after_restore",
    identity_keys=("server_name",),
)
async def restore_all(
    request: RestoreAllRequest, *, app_context: AppContext
) -> RestoreAllResponse:
    """Restores the server from the latest available backups."""
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
@track_operation(OperationName.BACKUP_RESTORE)
@trigger_event(
    before="before_restore",
    after="after_restore",
    identity_keys=("server_name",),
)
async def restore_world(
    request: RestoreWorldRequest, *, app_context: AppContext
) -> RestoreWorldResponse:
    """Restores a server's world from a specific backup file."""
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
                if backup_file_path.endswith(".bsmbackup"):
                    identifier = os.path.basename(backup_file_path)
                    if os.path.realpath(backup_file_path) != str(
                        server.backups.resolve_backup(identifier)
                    ):
                        raise ValueError("Backup must belong to this server.")
                    plan = await server.backups.plan_restore(identifier, ["world"])
                    await server.backups.restore_snapshot(
                        identifier, ["world"], plan.token
                    )
                else:
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
@track_operation(OperationName.BACKUP_RESTORE)
@trigger_event(
    before="before_restore",
    after="after_restore",
    identity_keys=("server_name",),
)
async def restore_config_file(
    request: RestoreConfigFileRequest, *, app_context: AppContext
) -> RestoreConfigFileResponse:
    """Restores a specific config file from a backup."""
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
                restored_file = await server.backups.restore_config(
                    backup_file_path, component=request.component
                )
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
    """Prunes old backups for a server based on retention settings."""
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
        result = await server.backups.prune_snapshots()
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


@api_method("create_server_backup")
@track_operation(OperationName.BACKUP_REQUEST)
@trigger_event(
    before="before_backup", after="after_backup", identity_keys=("server_name",)
)
async def create_server_backup(
    request: CreateSnapshotRequest, *, app_context: AppContext
) -> CreateSnapshotResponse:
    """Capture one coherent, optionally encrypted server archive."""
    server = app_context.get_server(request.server_name)
    snapshot = await server.backups.create_snapshot(
        encrypted=request.encrypted,
        mode=request.mode,
        components=request.components,
        purpose=request.purpose,
        _schedule_slot=request.schedule_slot,
        progress=app_context.task_manager.report_stage,
    )
    return CreateSnapshotResponse(
        server_name=request.server_name,
        message="Server backup created.",
        backup=snapshot,
    )


@api_method("list_server_snapshots")
async def list_server_snapshots(
    request: ListSnapshotsRequest, *, app_context: AppContext
) -> ListSnapshotsResponse:
    """List portable archives without decrypting their private manifests."""
    server = app_context.get_server(request.server_name, require_installation=False)
    return ListSnapshotsResponse(backups=await server.backups.list_snapshots())


@api_method("inspect_server_backup")
async def inspect_server_backup(
    request: InspectSnapshotRequest, *, app_context: AppContext
) -> InspectSnapshotResponse:
    """Authenticate a backup and return its manifest without secret file values."""
    server = app_context.get_server(request.server_name, require_installation=False)
    return InspectSnapshotResponse(
        backup=await server.backups.inspect_snapshot(
            request.backup_id,
            request.recovery_key.get_secret_value() if request.recovery_key else None,
        )
    )


@api_method("plan_server_restore")
async def plan_server_restore(
    request: PlanSnapshotRestoreRequest, *, app_context: AppContext
) -> PlanSnapshotRestoreResponse:
    """Validate selected contents and bind a restore plan to current destinations."""
    server = app_context.get_server(request.server_name, require_installation=False)
    return PlanSnapshotRestoreResponse(
        plan=await server.backups.plan_restore(
            request.backup_id,
            request.components,
            request.recovery_key.get_secret_value() if request.recovery_key else None,
        )
    )


@api_method("restore_server_snapshot")
@track_operation(OperationName.BACKUP_RESTORE)
@trigger_event(
    before="before_restore", after="after_restore", identity_keys=("server_name",)
)
async def restore_server_snapshot(
    request: RestoreSnapshotRequest, *, app_context: AppContext
) -> RestoreSnapshotResponse:
    """Apply a reviewed restore and keep restart failures separate from data recovery."""
    from ..api.models import StartServerRequest, StopServerRequest
    from ..api.server import start_server, stop_server

    server = app_context.get_server(request.server_name, require_installation=False)

    async def stop():
        await stop_server(
            StopServerRequest(server_name=request.server_name), app_context=app_context
        )

    async def start():
        await start_server(
            StartServerRequest(server_name=request.server_name), app_context=app_context
        )

    result = await server.backups.restore_snapshot(
        request.backup_id,
        request.components,
        request.token,
        request.recovery_key.get_secret_value() if request.recovery_key else None,
        stop_server=stop if request.stop_running else None,
        start_server=start,
        restart=request.restart,
        progress=app_context.task_manager.report_stage,
    )
    return RestoreSnapshotResponse(
        server_name=request.server_name,
        result=result,
        status=(
            "partial" if result.restart_error or result.cleanup_warning else "success"
        ),
        message="Selected backup components restored.",
    )


@api_method("get_restore_recovery")
async def get_restore_recovery(
    request: ListSnapshotsRequest, *, app_context: AppContext
) -> RestoreRecoveryResponse:
    """Inspect recovery state without exposing journal files or secret settings."""
    server = app_context.get_server(request.server_name, require_installation=False)
    return RestoreRecoveryResponse(recovery=await server.backups.recovery_state())


@api_method("recover_server_backup")
@track_operation(OperationName.BACKUP_RESTORE)
@trigger_event(
    before="before_restore", after="after_restore", identity_keys=("server_name",)
)
async def recover_server_backup(
    request: ListSnapshotsRequest, *, app_context: AppContext
) -> RestoreRecoveryResponse:
    """Retry an interrupted restore's recovery while preserving its journal on failure."""
    server = app_context.get_server(request.server_name, require_installation=False)
    return RestoreRecoveryResponse(
        recovery=await server.backups.recover_pending_restore()
    )


@api_method("get_backup_health")
async def get_backup_health(
    request: ListSnapshotsRequest, *, app_context: AppContext
) -> BackupHealthResponse:
    """Report durable backup health without opening secret archive contents."""
    server = app_context.get_server(request.server_name, require_installation=False)
    return BackupHealthResponse(health=await server.backups.backup_health())


@api_method("manage_server_snapshot")
async def manage_server_snapshot(
    request: ManageSnapshotRequest, *, app_context: AppContext
) -> ManageSnapshotResponse:
    """Verify, pin, copy, or test a recovery key against an authenticated archive."""
    backups = app_context.get_server(
        request.server_name, require_installation=False
    ).backups
    key = request.recovery_key.get_secret_value() if request.recovery_key else None
    from ..utils.progress import report_stage

    await report_stage(
        {
            "verify": "Verifying backup",
            "test_key": "Testing recovery key",
            "delete": "Deleting backup",
            "drill": "Testing backup recovery",
            "copy": "Copying backup",
            "annotate": "Updating backup notes",
            "pin": "Pinning backup",
            "unpin": "Unpinning backup",
        }.get(request.action, "Managing backup")
    )
    if request.action in ("verify", "test_key"):
        if request.action == "test_key" and not key:
            raise BackupRestoreError("Enter the recovery key from your emergency kit.")
        await backups.verify_snapshot(
            request.backup_id, key, record_failure=request.action != "test_key"
        )
    elif request.action == "delete":
        await backups.delete_snapshot(request.backup_id)
    elif request.action == "drill":
        from ..backups.assurance import recovery_drill

        await recovery_drill(backups, request.backup_id, key)
    elif request.action == "annotate":
        await backups.annotate_snapshot(request.backup_id, request.label, request.notes)
    elif request.action in ("pin", "unpin"):
        await backups.pin_snapshot(request.backup_id, request.action == "pin")
    else:
        if not request.destination:
            raise BackupRestoreError("Select a configured backup destination.")
        await backups.copy_snapshot(request.backup_id, request.destination)
    return ManageSnapshotResponse(message="Backup operation completed.")


@api_method("prepare_backup_copy")
@track_operation(OperationName.BACKUP_RESTORE)
async def prepare_backup_copy(
    request: PrepareBackupCopyRequest, *, app_context: AppContext
) -> PrepareBackupCopyResponse:
    """Install a stopped destination and publish a port-remapped archive for review."""
    from ..backups.clone import prepare_copy

    return await prepare_copy(request, app_context)


@api_method("can_reuse_server_backup")
async def can_reuse_server_backup(
    request: SnapshotReuseRequest, *, app_context: AppContext
) -> SnapshotReuseResponse:
    """Check coverage and availability without exposing archive paths or file values."""
    server = app_context.get_server(request.server_name, require_installation=False)
    return SnapshotReuseResponse(
        reusable=await server.backups.can_reuse_sequence_snapshot(
            mode=request.mode, components=request.components
        )
    )


@api_method("dry_run_server_restore")
async def dry_run_server_restore(
    request: PlanSnapshotRestoreRequest, *, app_context: AppContext
) -> PlanSnapshotRestoreResponse:
    """Validate and copy selected contents in isolation without stopping Minecraft."""
    server = app_context.get_server(request.server_name, require_installation=False)
    return PlanSnapshotRestoreResponse(
        plan=await server.backups.plan_restore(
            request.backup_id,
            request.components,
            request.recovery_key.get_secret_value() if request.recovery_key else None,
            dry_run=True,
        )
    )


@api_method("cleanup_backup_destination")
async def cleanup_backup_destination(
    request: CleanupBackupDestinationRequest, *, app_context: AppContext
) -> CleanupBackupDestinationResponse:
    """Preview external copy cleanup, or apply an unchanged reviewed plan."""
    from ..backups.assurance import cleanup_destination

    backups = app_context.get_server(
        request.server_name, require_installation=False
    ).backups
    return CleanupBackupDestinationResponse(
        plan=await cleanup_destination(backups, request.destination, request.token)
    )


@api_method("download_backup_recovery_report")
async def download_backup_recovery_report(
    request: ListSnapshotsRequest, *, app_context: AppContext
) -> RecoveryReportResponse:
    """Export allowlisted recovery evidence without file paths or secret values."""
    from ..backups.reports import recovery_report

    server = app_context.get_server(request.server_name, require_installation=False)
    return RecoveryReportResponse(report=await recovery_report(server.backups))
