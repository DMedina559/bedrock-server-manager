"""Snapshot download, import, decrypted export, and credential management helpers."""

import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any, AsyncIterator
from uuid import uuid4

from ..api.models.backup_restore import ListSnapshotsResponse
from ..utils.io import temporary_directory
from ..utils.progress import report_stage
from ..utils.threads import run_in_thread
from .archive import MAX_BYTES, publish_archive, write_archive
from .credentials import BackupCredentials, private_directory
from .recovery import sync_tree
from .work import backup_worker

if TYPE_CHECKING:
    from ..context import AppContext


class BackupUploadTooLargeError(ValueError):
    """Raised when an uploaded snapshot archive exceeds the configured size limit."""


async def open_snapshot_download(
    app_context: "AppContext", server_name: str, backup_id: str
) -> tuple[Path, int, AsyncIterator[bytes]]:
    """Open a snapshot archive for streaming download, retaining handle ownership on cancel."""
    backups = app_context.get_server(server_name, require_installation=False).backups
    stream: Any = None

    def open_archive() -> tuple[Path, int]:
        nonlocal stream
        path = backups.resolve_backup(backup_id)
        stream = path.open("rb")
        return path, os.fstat(stream.fileno()).st_size

    try:
        path, size = await run_in_thread(open_archive)
    except BaseException:
        if stream is not None:
            await run_in_thread(stream.close)
        raise

    async def chunks() -> AsyncIterator[bytes]:
        try:
            while chunk := await run_in_thread(stream.read, 1024 * 1024):
                yield chunk
        finally:
            await run_in_thread(stream.close)

    return path, size, chunks()


async def import_snapshot_upload(
    app_context: "AppContext",
    server_name: str,
    file: Any,
    recovery_key: str | None = None,
) -> ListSnapshotsResponse:
    """Validate an uploaded archive stream before publishing it under a fresh local ID."""
    backups = app_context.get_server(server_name, require_installation=False).backups
    try:
        async with backups.server.operation_lock:
            root = await run_in_thread(private_directory, Path(backups._directory()))
            async with temporary_directory(
                prefix=".bsm-import-", parent=root
            ) as directory:
                staging = Path(directory)
                archive = staging / "upload"
                size = 0
                await report_stage("Receiving backup upload")
                output: Any = None

                def open_upload() -> None:
                    nonlocal output
                    output = archive.open("wb")

                try:
                    await run_in_thread(open_upload)
                    while chunk := await file.read(1024 * 1024):
                        size += len(chunk)
                        if size > app_context.settings.get(
                            "backups.max_archive_bytes", MAX_BYTES
                        ):
                            raise BackupUploadTooLargeError(
                                "Backup exceeds upload limit."
                            )
                        await run_in_thread(output.write, chunk)
                finally:
                    if output is not None:
                        await run_in_thread(output.close)
                password = await run_in_thread(backups._password, archive, recovery_key)
                contents = await run_in_thread(private_directory, staging / "contents")
                manifest = await backup_worker(
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
                await report_stage("Publishing imported backup")
                await run_in_thread(publish_archive, archive, root / filename)
                await run_in_thread(backups._record_verified, root / filename, manifest)
                await run_in_thread(backups.catalog.update, filename, origin="imported")
            return ListSnapshotsResponse(backups=await backups.list_snapshots())
    finally:
        await file.close()


async def export_decrypted_snapshot(
    app_context: "AppContext",
    server_name: str,
    backup_id: str,
    recovery_key: str | None = None,
) -> AsyncIterator[bytes]:
    """Build and stream an unencrypted snapshot archive from private temporary storage."""
    backups = app_context.get_server(server_name, require_installation=False).backups
    temporary: Any = None
    stream: Any = None

    def create_export() -> None:
        nonlocal temporary
        temporary = tempfile.TemporaryDirectory(prefix="bsm-export-")

    def open_export(path: Path) -> None:
        nonlocal stream
        stream = path.open("rb")

    try:
        await run_in_thread(create_export)
        async with backups.server.operation_lock:
            staging = await run_in_thread(private_directory, Path(temporary.name))
            path = backups.resolve_backup(backup_id)
            password = await run_in_thread(
                backups._password,
                path,
                recovery_key,
            )
            contents = await run_in_thread(private_directory, staging / "contents")
            manifest = await backup_worker(
                backups.unpack_snapshot, path, contents, password
            )
            exported = staging / "plain.bsmbackup"
            await report_stage("Building decrypted export")
            await run_in_thread(write_archive, contents, exported, manifest, None, None)
        await run_in_thread(open_export, exported)
    except BaseException:
        if stream is not None:
            await run_in_thread(stream.close)
        if temporary is not None:
            await run_in_thread(temporary.cleanup)
        raise

    async def chunks() -> AsyncIterator[bytes]:
        try:
            while chunk := await run_in_thread(stream.read, 1024 * 1024):
                yield chunk
        finally:
            await run_in_thread(stream.close)
            await run_in_thread(temporary.cleanup)

    return chunks()


async def list_backup_keys(app_context: "AppContext") -> dict[str, Any]:
    """List key identifiers without exposing recovery credentials."""
    return await run_in_thread(BackupCredentials(app_context.config_dir).metadata)


async def rotate_backup_key(app_context: "AppContext") -> dict[str, str]:
    """Generate a new active key and retain all previous keys."""
    key = await run_in_thread(BackupCredentials(app_context.config_dir).rotate)
    return {"key_id": key.key_id, "created_at": key.created_at}


async def get_backup_emergency_kit(app_context: "AppContext", key_id: str) -> str:
    """Export one recovery credential for administrative download."""
    return await run_in_thread(
        BackupCredentials(app_context.config_dir).emergency_kit, key_id
    )
