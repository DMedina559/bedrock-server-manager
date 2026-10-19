# bedrock_server_manager/web/routers/backup_restore.py
"""FastAPI router for server backup, restore, and pruning operations."""

import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Callable, Literal
from uuid import uuid4

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
from pydantic import Field, SecretStr

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
    RestoreRecoveryResponse,
    RestoreSnapshotRequest,
)
from ...backups.archive import MAX_BYTES, write_archive
from ...backups.credentials import BackupCredentials, private_directory
from ...backups.models import Component, ConfigComponent
from ...backups.recovery import sync_tree
from ...context import AppContext
from ...utils.threads import run_in_thread
from ..deps import (
    get_admin_user,
    get_app_context,
    get_moderator_user,
    validate_server_exists,
)
from ..deps.server import validate_server_registered
from ..schemas import (
    BackupActionPayload,
    RestoreActionPayload,
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


class SnapshotCreatePayload(APIRequest):
    encrypted: bool | None = None
    include_packs: bool | None = None


class SnapshotInspectPayload(APIRequest):
    recovery_key: SecretStr | None = None


class SnapshotPlanPayload(SnapshotInspectPayload):
    components: list[Component]


class SnapshotRestorePayload(SnapshotPlanPayload):
    token: str
    restart: bool = True
    stop_running: bool = True


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
    backups = app_context.get_server(server_name, require_installation=False).backups
    await backups.server.operation_lock.acquire()
    try:
        path = backups.resolve_backup(backup_id)
        stream = await run_in_thread(path.open, "rb")
        size = os.fstat(stream.fileno()).st_size
        backups.server.operation_lock.release()
    except BaseException:
        backups.server.operation_lock.release()
        raise

    async def chunks():
        try:
            while chunk := await run_in_thread(stream.read, 1024 * 1024):
                yield chunk
        finally:
            stream.close()

    return StreamingResponse(
        chunks(),
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
    backups = app_context.get_server(server_name, require_installation=False).backups
    try:
        async with backups.server.operation_lock:
            root = await run_in_thread(private_directory, Path(backups._directory()))
            with tempfile.TemporaryDirectory(
                prefix=".bsm-import-", dir=root
            ) as directory:
                staging = Path(directory)
                archive = staging / "upload"
                size = 0
                with archive.open("wb") as output:
                    while chunk := await file.read(1024 * 1024):
                        size += len(chunk)
                        if size > app_context.settings.get(
                            "backups.max_archive_bytes", MAX_BYTES
                        ):
                            raise HTTPException(413, "Backup exceeds upload limit.")
                        await run_in_thread(output.write, chunk)
                password = await run_in_thread(backups._password, archive, recovery_key)
                contents = await run_in_thread(private_directory, staging / "contents")
                manifest = await run_in_thread(
                    backups.unpack_snapshot, archive, contents, password
                )
                filename = (
                    manifest.created_at.strftime("%Y%m%dT%H%M%SZ")
                    + "_"
                    + uuid4().hex
                    + ".bsmbackup"
                )
                await run_in_thread(
                    backups._validate_recovery_contents, contents, manifest
                )
                await run_in_thread(sync_tree, archive)
                await run_in_thread(os.replace, archive, root / filename)
                await run_in_thread(backups._record_verified, root / filename, manifest)
                await run_in_thread(backups.catalog.update, filename, origin="imported")
            return ListSnapshotsResponse(backups=await backups.list_snapshots())
    finally:
        await file.close()


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
    backups = app_context.get_server(server_name, require_installation=False).backups
    temporary = tempfile.TemporaryDirectory(prefix="bsm-export-")
    try:
        async with backups.server.operation_lock:
            staging = Path(temporary.name)
            path = backups.resolve_backup(backup_id)
            password = await run_in_thread(
                backups._password,
                path,
                (
                    payload.recovery_key.get_secret_value()
                    if payload.recovery_key
                    else None
                ),
            )
            contents = await run_in_thread(private_directory, staging / "contents")
            manifest = await run_in_thread(
                backups.unpack_snapshot, path, contents, password
            )
            exported = staging / "plain.bsmbackup"
            await run_in_thread(write_archive, contents, exported, manifest, None, None)
        stream = exported.open("rb")
    except BaseException:
        temporary.cleanup()
        raise

    async def chunks():
        try:
            while chunk := await run_in_thread(stream.read, 1024 * 1024):
                yield chunk
        finally:
            stream.close()
            await run_in_thread(temporary.cleanup)

    return StreamingResponse(
        chunks(),
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
    return await run_in_thread(BackupCredentials(app_context.config_dir).metadata)


@router.post("/api/backups/keys", operation_id="rotate_backup_key")
async def rotate_key(
    current_user: UserResponse = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
) -> dict[str, str]:
    """Generate a new active key and retain all previous keys."""
    key = await run_in_thread(BackupCredentials(app_context.config_dir).rotate)
    return {"key_id": key.key_id, "created_at": key.created_at}


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
    kit = await run_in_thread(
        BackupCredentials(app_context.config_dir).emergency_kit, key_id
    )
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


class SnapshotManagePayload(SnapshotInspectPayload):
    action: Literal["verify", "pin", "unpin", "copy", "test_key", "annotate", "drill"]
    destination: str | None = None
    label: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None, max_length=2000)


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


class SnapshotCopyPayload(SnapshotInspectPayload):
    target_server: str
    target_version: str = "LATEST"
    server_port: int = Field(ge=1, le=65535)
    server_portv6: int = Field(ge=1, le=65535)


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


class DestinationCleanupPayload(APIRequest):
    token: str | None = None


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
