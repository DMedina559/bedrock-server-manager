# bedrock_server_manager/web/routers/backup_restore.py
"""FastAPI router for server backup, restore, and pruning operations."""

import logging
import os
from typing import Any, Callable

import aiofiles.ospath
from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.responses import Response, StreamingResponse

from bedrock_server_manager.api.models import (
    APIRequest,
    BackupAllRequest,
    BackupConfigFileRequest,
    BackupWorldRequest,
    ListBackupFilesRequest,
    PruneOldBackupsRequest,
    RestoreAllRequest,
    RestoreConfigFileRequest,
    RestoreWorldRequest,
)

from ...api import backup_restore as backup_restore_api
from ...api.models.backup_restore import (
    BackupHealthResponse,
    CleanupBackupDestinationRequest,
    CreateSnapshotRequest,
    InspectSnapshotRequest,
    ListSnapshotsRequest,
    ListSnapshotsResponse,
    ManageSnapshotRequest,
    PlanSnapshotRestoreRequest,
    PrepareBackupCopyRequest,
    RecoveryReportResponse,
    RestoreRecoveryResponse,
    RestoreSnapshotRequest,
)
from ...backups import transfer as backup_transfer
from ...backups.models import ConfigComponent
from ...context import AppContext
from ..deps import (
    get_admin_user,
    get_app_context,
    get_moderator_user,
    validate_server_exists,
)
from ..deps.server import validate_server_registered
from ..schemas import (
    BackupActionPayload,
    DestinationCleanupPayload,
    RestoreActionPayload,
    SnapshotCopyPayload,
    SnapshotCreatePayload,
    SnapshotInspectPayload,
    SnapshotManagePayload,
    SnapshotPlanPayload,
    SnapshotRestorePayload,
    UserResponse,
)
from ..schemas.base import BackupFilesResponse, TaskAcceptedResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Backup & Restore"])
LEGACY_COMPONENTS: dict[str, ConfigComponent] = {
    "properties": "server.properties",
    "allowlist": "allowlist.json",
    "permissions": "permissions.json",
}


# --- API Routes ---
@router.put(
    "/api/server/{server_name}/backups/prune",
    operation_id="prune_backups",
    response_model=TaskAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def put_prune_backups(
    server_name: str = Depends(validate_server_registered),
    current_user: UserResponse = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
) -> TaskAcceptedResponse:
    """
    Initiates a background task to prune old backups for a specific server.

    This action adheres to the retention policies defined in the application settings.
    """
    identity = current_user.username
    logger.info(
        "Request to prune backups for server '%s' by user '%s'.", server_name, identity
    )
    task_id = await app_context.task_manager.run_task(
        backup_restore_api.prune_old_backups,
        username=current_user.username,
        app_context=app_context,
        request=PruneOldBackupsRequest.model_validate({"server_name": server_name}),
    )

    return TaskAcceptedResponse(
        status="accepted",
        message=f"Backup pruning for server '{server_name}' initiated in background.",
        task_id=task_id,
    )


@router.get(
    "/api/server/{server_name}/backup/list/{backup_type}",
    operation_id="list_server_backups",
    response_model=BackupFilesResponse,
)
async def get_list_server_backups(
    backup_type: str,
    server_name: str = Depends(validate_server_registered),
    current_user: UserResponse = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
) -> BackupFilesResponse:
    """
    Lists available backup files for a specific server and backup type.
    """
    identity = current_user.username
    logger.debug(
        "Request to list '%s' backups for server '%s' by user '%s'.",
        backup_type,
        server_name,
        identity,
    )
    api_result = await backup_restore_api.list_backup_files(
        request=ListBackupFilesRequest.model_validate(
            {"server_name": server_name, "backup_type": backup_type}
        ),
        app_context=app_context,
    )
    backup_data = api_result.backups

    if backup_type.lower() == "all" and isinstance(backup_data, dict):
        # For 'all', backup_data is Dict[str, List[str (full paths)]]
        # We need to convert full paths to basenames for each list in the dict
        processed_all_backups = {
            key: [os.path.basename(p) for p in path_list]
            for key, path_list in backup_data.items()
        }
        return BackupFilesResponse(
            status="success",
            message="All backup types listed successfully.",
            backups=processed_all_backups,
        )
    elif isinstance(backup_data, list):
        basenames = [os.path.basename(p) for p in backup_data]
        return BackupFilesResponse(
            status="success",
            message="Backups listed successfully.",
            backups=basenames,
        )
    else:
        logger.error(
            "Invalid backup listing format for type '%s'.",
            backup_type,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected backup data format.",
        )


@router.post(
    "/api/server/{server_name}/backup/action",
    operation_id="create_backup",
    response_model=TaskAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def post_backup_action(
    server_name: str = Depends(validate_server_exists),
    payload: BackupActionPayload = Body(...),
    current_user: UserResponse = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
) -> TaskAcceptedResponse:
    """Initiates a background task to perform a backup action for a specific server.

    Valid backup types are "world", "config" (requires ``file_to_backup`` in payload),
    and "all".
    """
    identity = current_user.username
    logger.info(
        "Backup action '%s' requested for server '%s' by user '%s'.",
        payload.backup_type,
        server_name,
        identity,
    )
    valid_types = ["world", "config", "all"]
    if payload.backup_type.lower() not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid 'backup_type'. Must be one of: {valid_types}.",
        )

    if payload.backup_type.lower() == "config" and (
        not payload.file_to_backup or not isinstance(payload.file_to_backup, str)
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing or invalid 'file_to_backup' for config backup type.",
        )

    target_func: Callable[..., Any]
    request: APIRequest
    if payload.backup_type.lower() == "world":
        target_func = backup_restore_api.backup_world
        request = BackupWorldRequest(server_name=server_name)
    elif payload.backup_type.lower() == "config":
        target_func = backup_restore_api.backup_config_file
        assert payload.file_to_backup is not None
        request = BackupConfigFileRequest(
            server_name=server_name, file_to_backup=payload.file_to_backup.strip()
        )
    else:
        target_func = backup_restore_api.backup_all
        request = BackupAllRequest(server_name=server_name)

    task_id = await app_context.task_manager.run_task(
        target_func,
        username=current_user.username,
        request=request,
        app_context=app_context,
    )

    return TaskAcceptedResponse(
        status="accepted",
        message=f"Backup action '{payload.backup_type}' for server '{server_name}' initiated in background.",
        task_id=task_id,
    )


@router.post(
    "/api/server/{server_name}/restore/action",
    operation_id="restore_backup",
    response_model=TaskAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def post_restore_action(  # noqa: C901
    payload: RestoreActionPayload,
    server_name: str = Depends(validate_server_registered),
    current_user: UserResponse = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
) -> TaskAcceptedResponse:
    """Initiates a background task to perform a restore action for a specific server.

    Valid restore types include "all", "world", "properties", "allowlist", and
    "permissions". If not restoring "all", a ``backup_file`` (basename) must be
    provided in the payload.
    """
    identity = current_user.username
    logger.info(
        "Restore action '%s' requested for server '%s' by user '%s'.",
        payload.restore_type,
        server_name,
        identity,
    )
    valid_types = ["world", "properties", "allowlist", "permissions", "all"]
    restore_type_lower = payload.restore_type.lower()

    if restore_type_lower not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid 'restore_type'. Must be one of: {valid_types}.",
        )

    if restore_type_lower != "all" and (
        not payload.backup_file or not isinstance(payload.backup_file, str)
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing or invalid 'backup_file' for this restore type.",
        )

    if payload.backup_file and (
        ".." in payload.backup_file or payload.backup_file.startswith(("/", "\\"))
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid 'backup_file' path.",
        )

    # Re-assert for mypy that payload.backup_file is str if we continue
    backup_file_name: str = payload.backup_file if payload.backup_file else ""

    target_func: Callable[..., Any]
    request: APIRequest

    if restore_type_lower == "all":
        target_func = backup_restore_api.restore_all
        request = RestoreAllRequest(server_name=server_name)
    else:
        backup_base_dir = app_context.settings.get("paths.backups")
        if not backup_base_dir:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="BACKUP_DIR not configured.",
            )

        server_backup_dir = os.path.join(backup_base_dir, server_name)
        full_backup_path = os.path.normpath(
            os.path.join(server_backup_dir, backup_file_name)
        )

        if not os.path.abspath(full_backup_path).startswith(
            os.path.abspath(server_backup_dir) + os.sep
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Security violation - Invalid backup path '{backup_file_name}'.",
            )

        if not await aiofiles.ospath.isfile(full_backup_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Backup file not found: {full_backup_path}",
            )

        if restore_type_lower == "world":
            target_func = backup_restore_api.restore_world
            request = RestoreWorldRequest(
                server_name=server_name, backup_file_path=full_backup_path
            )
        else:
            target_func = backup_restore_api.restore_config_file
            request = RestoreConfigFileRequest(
                server_name=server_name,
                backup_file_path=full_backup_path,
                component=LEGACY_COMPONENTS[restore_type_lower],
            )

    task_id = await app_context.task_manager.run_task(
        target_func,
        username=current_user.username,
        request=request,
        app_context=app_context,
    )

    return TaskAcceptedResponse(
        status="accepted",
        message=f"Restore action '{payload.restore_type}' for server '{server_name}' initiated in background.",
        task_id=task_id,
    )


# Portable archive endpoints. Existing category endpoints are legacy adapters.


def _request(payload, model, server_name, **extra):
    values = payload.model_dump()
    if hasattr(payload, "recovery_key"):
        values["recovery_key"] = payload.recovery_key
    return model(server_name=server_name, **values, **extra)


async def _accepted(context, user, function, request) -> TaskAcceptedResponse:
    task_id = await context.task_manager.run_task(
        function, username=user.username, app_context=context, request=request
    )
    return TaskAcceptedResponse(
        status="accepted", task_id=task_id, message="Backup operation accepted."
    )


@router.get(
    "/api/server/{server_name}/backups",
    operation_id="list_server_snapshots",
    response_model=ListSnapshotsResponse,
)
async def get_snapshots(
    server_name: str = Depends(validate_server_registered),
    current_user: UserResponse = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
) -> ListSnapshotsResponse:
    """List completed portable server backup archives."""
    return await backup_restore_api.list_server_snapshots(
        ListSnapshotsRequest(server_name=server_name), app_context=app_context
    )


@router.post(
    "/api/server/{server_name}/backups",
    operation_id="create_server_snapshot",
    response_model=TaskAcceptedResponse,
    status_code=202,
)
async def post_snapshot(
    payload: SnapshotCreatePayload,
    server_name: str = Depends(validate_server_exists),
    current_user: UserResponse = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
) -> TaskAcceptedResponse:
    """Capture one server backup using the configured encryption default."""
    return await _accepted(
        app_context,
        current_user,
        backup_restore_api.create_server_backup,
        _request(payload, CreateSnapshotRequest, server_name),
    )


@router.post(
    "/api/server/{server_name}/backups/{backup_id}/inspect",
    operation_id="inspect_server_snapshot",
    response_model=TaskAcceptedResponse,
    status_code=202,
)
async def post_inspect(
    backup_id: str,
    payload: SnapshotInspectPayload,
    server_name: str = Depends(validate_server_registered),
    current_user: UserResponse = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
) -> TaskAcceptedResponse:
    """Authenticate an archive before displaying its private component inventory."""
    return await _accepted(
        app_context,
        current_user,
        backup_restore_api.inspect_server_backup,
        _request(payload, InspectSnapshotRequest, server_name, backup_id=backup_id),
    )


@router.post(
    "/api/server/{server_name}/backups/{backup_id}/plan",
    operation_id="plan_snapshot_restore",
    response_model=TaskAcceptedResponse,
    status_code=202,
)
async def post_plan(
    backup_id: str,
    payload: SnapshotPlanPayload,
    server_name: str = Depends(validate_server_registered),
    current_user: UserResponse = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
) -> TaskAcceptedResponse:
    """Prepare a reviewed selection without stopping the Minecraft server."""
    return await _accepted(
        app_context,
        current_user,
        backup_restore_api.plan_server_restore,
        _request(payload, PlanSnapshotRestoreRequest, server_name, backup_id=backup_id),
    )


@router.post(
    "/api/server/{server_name}/backups/{backup_id}/restore",
    operation_id="restore_server_snapshot",
    response_model=TaskAcceptedResponse,
    status_code=202,
)
async def post_snapshot_restore(
    backup_id: str,
    payload: SnapshotRestorePayload,
    server_name: str = Depends(validate_server_registered),
    current_user: UserResponse = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
) -> TaskAcceptedResponse:
    """Restore explicitly selected components using a current review token."""
    return await _accepted(
        app_context,
        current_user,
        backup_restore_api.restore_server_snapshot,
        _request(payload, RestoreSnapshotRequest, server_name, backup_id=backup_id),
    )


@router.get(
    "/api/server/{server_name}/backups/{backup_id}/download",
    operation_id="download_server_snapshot",
    response_class=StreamingResponse,
    responses={
        200: {
            "content": {
                "application/octet-stream": {
                    "schema": {"type": "string", "format": "binary"}
                }
            }
        }
    },
)
async def download_snapshot(
    backup_id: str,
    server_name: str = Depends(validate_server_registered),
    current_user: UserResponse = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
) -> StreamingResponse:
    """Download the stored archive unchanged, preserving encryption."""
    try:
        path, size, stream = await backup_transfer.open_snapshot_download(
            app_context, server_name, backup_id
        )
    except FileNotFoundError as error:
        raise HTTPException(404, "Backup no longer exists.") from error

    return StreamingResponse(
        stream,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{path.name}"',
            "Content-Length": str(size),
            "Cache-Control": "no-store",
        },
    )


@router.post(
    "/api/server/{server_name}/backups/import",
    operation_id="import_server_snapshot",
    response_model=ListSnapshotsResponse,
)
async def import_snapshot(
    file: UploadFile = File(..., json_schema_extra={"format": "binary"}),
    recovery_key: str | None = Form(None),
    server_name: str = Depends(validate_server_registered),
    current_user: UserResponse = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
) -> ListSnapshotsResponse:
    """Validate an uploaded archive before publishing it under a fresh local ID."""
    try:
        return await backup_transfer.import_snapshot_upload(
            app_context, server_name, file, recovery_key
        )
    except backup_transfer.BackupUploadTooLargeError as error:
        raise HTTPException(413, str(error)) from error


@router.post(
    "/api/server/{server_name}/backups/{backup_id}/export",
    operation_id="export_decrypted_snapshot",
    response_class=StreamingResponse,
    responses={
        200: {
            "content": {
                "application/octet-stream": {
                    "schema": {"type": "string", "format": "binary"}
                }
            }
        }
    },
)
async def export_snapshot(
    backup_id: str,
    payload: SnapshotInspectPayload,
    server_name: str = Depends(validate_server_registered),
    current_user: UserResponse = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
) -> StreamingResponse:
    """Explicitly export an unencrypted archive; temporary files remain private."""
    stream = await backup_transfer.export_decrypted_snapshot(
        app_context,
        server_name,
        backup_id,
        payload.recovery_key.get_secret_value() if payload.recovery_key else None,
    )
    return StreamingResponse(
        stream,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": 'attachment; filename="decrypted.bsmbackup"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/api/backups/keys", operation_id="list_backup_keys")
async def list_keys(
    current_user: UserResponse = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
) -> dict[str, Any]:
    """List key identifiers without exposing recovery credentials."""
    return await backup_transfer.list_backup_keys(app_context)


@router.post("/api/backups/keys", operation_id="rotate_backup_key")
async def rotate_key(
    current_user: UserResponse = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
) -> dict[str, str]:
    """Generate a new active key and retain all previous keys."""
    return await backup_transfer.rotate_backup_key(app_context)


@router.get(
    "/api/backups/keys/{key_id}/emergency-kit",
    operation_id="download_backup_emergency_kit",
    response_class=Response,
    responses={200: {"content": {"text/plain": {"schema": {"type": "string"}}}}},
)
async def emergency_kit(
    key_id: str,
    current_user: UserResponse = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
) -> Response:
    """Export one recovery credential through a dedicated administrative route."""
    kit = await backup_transfer.get_backup_emergency_kit(app_context, key_id)
    return Response(
        kit,
        media_type="text/plain",
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": 'attachment; filename="bsm-backup-emergency-kit.txt"',
        },
    )


@router.get(
    "/api/server/{server_name}/backups/recovery",
    operation_id="get_restore_recovery",
    response_model=RestoreRecoveryResponse,
)
async def get_recovery(
    server_name: str = Depends(validate_server_registered),
    current_user: UserResponse = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
) -> RestoreRecoveryResponse:
    """Inspect whether a restore journal needs attention."""
    return await backup_restore_api.get_restore_recovery(
        ListSnapshotsRequest(server_name=server_name), app_context=app_context
    )


@router.post(
    "/api/server/{server_name}/backups/recovery",
    operation_id="recover_server_backup",
    response_model=TaskAcceptedResponse,
    status_code=202,
)
async def retry_recovery(
    server_name: str = Depends(validate_server_registered),
    current_user: UserResponse = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
) -> TaskAcceptedResponse:
    """Retry journal recovery; stop a running server before rolling back data."""
    return await _accepted(
        app_context,
        current_user,
        backup_restore_api.recover_server_backup,
        ListSnapshotsRequest(server_name=server_name),
    )


@router.get(
    "/api/server/{server_name}/backups/health",
    operation_id="get_backup_health",
    response_model=BackupHealthResponse,
)
async def backup_health(
    server_name: str = Depends(validate_server_registered),
    current_user: UserResponse = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
) -> BackupHealthResponse:
    """Read backup verification, storage and key health."""
    return await backup_restore_api.get_backup_health(
        ListSnapshotsRequest(server_name=server_name), app_context=app_context
    )


@router.post(
    "/api/server/{server_name}/backups/{backup_id}/manage",
    operation_id="manage_server_snapshot",
    response_model=TaskAcceptedResponse,
    status_code=202,
)
async def manage_snapshot(
    backup_id: str,
    payload: SnapshotManagePayload,
    server_name: str = Depends(validate_server_registered),
    current_user: UserResponse = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
) -> TaskAcceptedResponse:
    """Verify, pin, retry a destination copy, or test an emergency recovery key."""
    return await _accepted(
        app_context,
        current_user,
        backup_restore_api.manage_server_snapshot,
        _request(payload, ManageSnapshotRequest, server_name, backup_id=backup_id),
    )


@router.post(
    "/api/server/{server_name}/backups/{backup_id}/prepare-copy",
    operation_id="prepare_backup_copy",
    response_model=TaskAcceptedResponse,
    status_code=202,
)
async def prepare_backup_copy(
    backup_id: str,
    payload: SnapshotCopyPayload,
    server_name: str = Depends(validate_server_registered),
    current_user: UserResponse = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
) -> TaskAcceptedResponse:
    """Prepare a stopped new server; review its component restore separately."""
    return await _accepted(
        app_context,
        current_user,
        backup_restore_api.prepare_backup_copy,
        _request(payload, PrepareBackupCopyRequest, server_name, backup_id=backup_id),
    )


@router.post(
    "/api/server/{server_name}/backups/{backup_id}/dry-run",
    operation_id="dry_run_server_restore",
    response_model=TaskAcceptedResponse,
    status_code=202,
)
async def dry_run_restore(
    backup_id: str,
    payload: SnapshotPlanPayload,
    server_name: str = Depends(validate_server_registered),
    current_user: UserResponse = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
) -> TaskAcceptedResponse:
    """Validate an isolated restore without stopping or modifying the server."""
    return await _accepted(
        app_context,
        current_user,
        backup_restore_api.dry_run_server_restore,
        _request(payload, PlanSnapshotRestoreRequest, server_name, backup_id=backup_id),
    )


@router.post(
    "/api/server/{server_name}/backup-destinations/{destination}/cleanup",
    operation_id="cleanup_backup_destination",
    response_model=TaskAcceptedResponse,
    status_code=202,
)
async def cleanup_destination(
    destination: str,
    payload: DestinationCleanupPayload,
    server_name: str = Depends(validate_server_registered),
    current_user: UserResponse = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
) -> TaskAcceptedResponse:
    """Preview external cleanup; a reviewed token explicitly authorizes deletion."""
    return await _accepted(
        app_context,
        current_user,
        backup_restore_api.cleanup_backup_destination,
        CleanupBackupDestinationRequest(
            server_name=server_name, destination=destination, token=payload.token
        ),
    )


@router.get(
    "/api/server/{server_name}/backups/report",
    operation_id="download_backup_recovery_report",
    response_model=RecoveryReportResponse,
)
async def download_recovery_report(
    server_name: str = Depends(validate_server_registered),
    current_user: UserResponse = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
) -> Response:
    """Download a redacted JSON recovery report."""
    result = await backup_restore_api.download_backup_recovery_report(
        ListSnapshotsRequest(server_name=server_name), app_context=app_context
    )
    return Response(
        content=result.model_dump_json(indent=2),
        media_type="application/json",
        headers={
            "Content-Disposition": 'attachment; filename="bsm-recovery-report.json"',
            "Cache-Control": "no-store",
        },
    )
