"""Unified server snapshots with selective restore and persistent recovery."""

import asyncio
import hashlib
import json
import logging
import os
import platform
import shutil
import stat
import threading
import time
from contextlib import AsyncExitStack, ExitStack
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Awaitable, Callable, Literal
from uuid import uuid4

from pydantic import SecretStr

from ..config.const import get_installed_version
from ..contracts import CleanupResult, CompletedItem, ComponentResults, SkippedItem
from ..error import BackupRestoreError, ConfigurationError
from ..events.operations import OperationName
from ..logging import log_operation_error
from ..utils.io import temporary_directory
from ..utils.progress import report_stage
from ..utils.threads import check_cancellation, run_in_thread
from .archive import (
    build_payload,
    check_manifest_limits,
    digest,
    header,
    publish_archive,
    safe_name,
    unpack,
    write_archive,
)
from .catalog import ManagedBackups, now
from .contents import SelectableComponent
from .credentials import (
    BackupCredentials,
    KeyRecord,
    key_id,
    private_directory,
    protect,
)
from .models import (
    COMPONENTS,
    PACK_COMPONENTS,
    PREFIXES,
    BackupFile,
    BackupManifest,
    BackupMode,
    BackupSummary,
    Component,
    RestorePlan,
    RestoreRecoveryState,
    RestoreResult,
    ServerSettingsExport,
)
from .recovery import RestoreJournal, apply_settings, settings_export
from .selection import selection, server_entries
from .spool import CaptureSpool
from .work import FileWork, backup_worker, tree_paths

if TYPE_CHECKING:
    from ..core.bedrock_server import BedrockServer


def is_link(source: Path) -> bool:
    return source.is_symlink() or bool(
        getattr(source.lstat(), "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    )


def _close_copy_stream(stream, work, phase):
    with work.phase(phase):
        stream.close()


def copy_source(
    source: Path,
    target: Path,
    cancellation_event: threading.Event | None = None,
    *,
    hashes: dict[Path, tuple[int, int, str]] | None = None,
    inherited_private: bool = False,
    spool: CaptureSpool | None = None,
    stage_callback=None,
) -> None:
    """Sequential portable copy with aggregate timing and bounded progress."""
    work = FileWork("Copying backup files", stage_callback)
    status = "failed"
    try:
        work.progress(force=True)
        _copy_source(
            source,
            target,
            cancellation_event,
            hashes=hashes,
            inherited_private=inherited_private,
            spool=spool,
            work=work,
        )
        work.progress(force=True)
        status = "completed"
    finally:
        work.finish(status)


def _copy_source(
    source: Path,
    target: Path,
    cancellation_event: threading.Event | None = None,
    *,
    hashes: dict[Path, tuple[int, int, str]] | None = None,
    inherited_private: bool = False,
    spool: CaptureSpool | None = None,
    work: FileWork,
) -> None:
    """Copy only portable regular files and directories, never following links."""
    check_cancellation(cancellation_event)
    safe_name(source.name)
    with work.phase("metadata"):
        linked = is_link(source)
        directory = source.is_dir()
        regular = source.is_file()
    if linked:
        raise BackupRestoreError("Backup sources must not contain symbolic links.")
    if directory:
        with work.phase("metadata"):
            target.mkdir(parents=True, exist_ok=True)
        for child in source.iterdir():
            _copy_source(
                child,
                target / child.name,
                cancellation_event,
                hashes=hashes,
                inherited_private=inherited_private,
                spool=spool,
                work=work,
            )
    elif regular:
        with work.phase("metadata"):
            target.parent.mkdir(parents=True, exist_ok=True)
        hasher = hashlib.sha256() if hashes is not None else None
        spool_stream = spool.stream if spool is not None else None
        offset = spool_stream.tell() if spool_stream is not None else 0

        def captured(chunk: bytes) -> None:
            if hasher is not None:
                hasher.update(chunk)
            if spool_stream is not None:
                spool_stream.write(chunk)

        with ExitStack() as resources:
            with work.phase("source_open"):
                stream = source.open("rb")
            resources.callback(_close_copy_stream, stream, work, "source_close")
            with work.phase("target_open"):
                output = target.open("wb")
            resources.callback(_close_copy_stream, output, work, "target_close")
            while True:
                check_cancellation(cancellation_event)
                with work.phase("read"):
                    chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                check_cancellation(cancellation_event)
                with work.phase("write"):
                    output.write(chunk)
                if hasher is not None or spool_stream is not None:
                    with work.phase("hash_spool"):
                        captured(chunk)
                work.bytes += len(chunk)
                work.progress()
            with work.phase("permissions"):
                if not (inherited_private and os.name == "nt"):
                    protect(target)
                if os.name != "nt" and source.stat().st_mode & stat.S_IXUSR:
                    target.chmod(0o700)

        work.files += 1
        work.progress()
        if spool is not None:
            metadata = target.stat()
            spool.entries[target] = (metadata.st_size, metadata.st_mtime_ns, offset)
        if hashes is not None and hasher is not None:
            metadata = target.stat()
            hashes[target] = (
                metadata.st_size,
                metadata.st_mtime_ns,
                hasher.hexdigest(),
            )
    else:
        raise BackupRestoreError("Backup source is not a regular file or directory.")


def inventory(
    staging: Path,
    components,
    cancellation_event: threading.Event | None = None,
    *,
    hashes: dict[Path, tuple[int, int, str]] | None = None,
) -> tuple[list[BackupFile], list[str]]:
    files = []
    directories = []
    for component, state in components.items():
        if state != "included":
            continue
        root = staging / PREFIXES[component]
        paths = sorted(tree_paths(root, cancellation_event))
        for path in paths:
            check_cancellation(cancellation_event)
            name = safe_name(path.relative_to(staging).as_posix())
            if path.is_dir():
                directories.append(name)
            else:
                metadata = path.stat()
                cached = hashes.get(path) if hashes is not None else None
                checksum = (
                    cached[2]
                    if cached is not None
                    and cached[:2] == (metadata.st_size, metadata.st_mtime_ns)
                    else digest(path, cancellation_event)
                )
                files.append(
                    BackupFile(
                        path=name,
                        component=component,
                        size=metadata.st_size,
                        sha256=checksum,
                        executable=bool(metadata.st_mode & stat.S_IXUSR),
                    )
                )
    return files, directories


def verify_staging(
    root, manifest, components, cancellation_event=None, stage_callback=None
):
    """Read back staged files with bounded progress and aggregate I/O timings."""
    work = FileWork("Checking staged restore checksums", stage_callback)
    status = "failed"
    try:
        work.progress(force=True)
        for item in manifest.files:
            check_cancellation(cancellation_event)
            if item.component not in components:
                continue
            checksum = hashlib.sha256()
            with work.phase("open"):
                stream = (root / item.path).open("rb")
            try:
                while True:
                    check_cancellation(cancellation_event)
                    with work.phase("read"):
                        chunk = stream.read(1024 * 1024)
                    if not chunk:
                        break
                    check_cancellation(cancellation_event)
                    with work.phase("hash"):
                        checksum.update(chunk)
                    work.bytes += len(chunk)
                    work.progress()
            finally:
                with work.phase("close"):
                    stream.close()
            if checksum.hexdigest() != item.sha256:
                raise BackupRestoreError("Staged restore checksum validation failed.")
            work.files += 1
            work.progress()
        work.progress(force=True)
        status = "completed"
        return work.files
    finally:
        work.finish(status)


class UnifiedServerBackups(ManagedBackups):
    """Share one capture implementation between manual and automatic callers."""

    server: "BedrockServer"
    logger: logging.LoggerAdapter

    def _directory(self) -> str:
        root = self.server.settings.get("paths.backups")
        if not root:
            raise ConfigurationError("Backup directory is not configured.")
        return str(Path(root) / self.server.server_name)

    async def recovery_state(self) -> RestoreRecoveryState:
        journal = RestoreJournal(self.server)
        if not journal.path.exists():
            return RestoreRecoveryState(active=False)
        try:
            state = await run_in_thread(journal._load)
            return RestoreRecoveryState(active=True, committed=state["committed"])
        except Exception:
            return RestoreRecoveryState(
                active=True,
                error="Recovery journal needs manual inspection. Preserve its contents.",
            )

    async def recover_pending_restore(self) -> RestoreRecoveryState:
        if self.server.state is None:
            raise BackupRestoreError("Server state is unavailable.")
        async with self.server.operation_lock:
            with self.server.state.servers.maintenance(self.server.server_name).hold():
                await RestoreJournal(self.server).recover()
                return await self.recovery_state()

    @property
    def credentials(self) -> BackupCredentials:
        return BackupCredentials(self.server.settings.config_dir)

    def unpack_snapshot(
        self,
        path: Path,
        destination: Path,
        password: str | None = None,
        cancellation_event: threading.Event | None = None,
        *,
        materialize: bool = True,
        stage_callback=None,
        read_stats=None,
        durable: bool = False,
    ) -> BackupManifest:
        if path.stat().st_size > self.server.settings.get(
            "backups.max_archive_bytes", 1024**4
        ):
            raise BackupRestoreError("Archive exceeds configured size limit.")
        return unpack(
            path,
            destination,
            password,
            max_bytes=self.server.settings.get("backups.max_expanded_bytes", 1024**4),
            max_files=self.server.settings.get("backups.max_files", 1_000_000),
            cancellation_event=cancellation_event,
            materialize=materialize,
            stage_callback=stage_callback,
            read_stats=read_stats,
            durable=durable,
        )

    def resolve_backup(self, identifier: str) -> Path:
        safe_name(identifier)
        if Path(identifier).name != identifier:
            raise BackupRestoreError("Backup ID must be a local filename.")
        root = Path(self._directory()).resolve()
        path = root / identifier
        if path.is_symlink() or not path.is_file() or path.resolve().parent != root:
            raise BackupRestoreError(
                "Backup does not exist in this server's backup directory."
            )
        return path

    def _password(self, path: Path, supplied: str | None) -> str | None:
        info = header(path)
        if not info.encrypted:
            return None
        if supplied is not None:
            return supplied
        try:
            return self.credentials.get(info.key_id).secret.get_secret_value()
        except ConfigurationError as error:
            raise BackupRestoreError(
                "This backup requires its recovery key."
            ) from error

    async def _stage(self, progress, message: str) -> None:
        self.logger.debug("Backup/restore stage: %s", message)
        if progress is not None:
            await progress(message)
        else:
            await report_stage(message)

    async def create_snapshot(
        self,
        *,
        encrypted: bool | None = None,
        purpose: Literal[
            "manual", "pre_start", "pre_update", "pre_restore", "scheduled"
        ] = "manual",
        progress: Callable[[str], Awaitable[None]] | None = None,
        _safety_world: str | None = None,
        _safety_password: str | None = None,
        _schedule_slot: str | None = None,
        mode: BackupMode | None = None,
        components: list[SelectableComponent] | None = None,
    ) -> BackupSummary:
        started = time.monotonic()
        last_stage = "Waiting for backup operation lock"
        original_progress = progress

        async def capture_progress(message: str) -> None:
            nonlocal last_stage
            last_stage = message
            if original_progress is not None:
                await original_progress(message)
            else:
                await report_stage(message)

        try:
            result = await self._create_snapshot(
                encrypted=encrypted,
                purpose=purpose,
                progress=capture_progress,
                _safety_world=_safety_world,
                _safety_password=_safety_password,
                _schedule_slot=_schedule_slot,
                mode=mode,
                components=components,
            )
            self.logger.info(
                "Backup capture completed in %.3f seconds", time.monotonic() - started
            )
            return result
        except asyncio.CancelledError:
            self.logger.warning(
                "Backup capture cancelled during '%s' after %.3f seconds; cancellation may originate from a caller or hook deadline",
                last_stage,
                time.monotonic() - started,
            )
            raise
        except Exception as error:
            log_operation_error(
                self.logger,
                "Backup capture failed during '%s' after %.3f seconds",
                last_stage,
                time.monotonic() - started,
                error=error,
            )
            async with self.server.operation_lock:
                value = await run_in_thread(self.catalog.load)
                value.update(
                    last_failure_at=now(),
                    last_error="Backup capture failed; inspect application logs.",
                )
                await run_in_thread(self.catalog.save, value)
            raise

    async def _create_snapshot(
        self,
        *,
        encrypted: bool | None = None,
        purpose: Literal[
            "manual", "pre_start", "pre_update", "pre_restore", "scheduled"
        ] = "manual",
        progress: Callable[[str], Awaitable[None]] | None = None,
        _safety_world: str | None = None,
        _safety_password: str | None = None,
        _schedule_slot: str | None = None,
        mode: BackupMode | None = None,
        components: list[SelectableComponent] | None = None,
    ) -> BackupSummary:
        import time

        stages: dict[str, float] = {}
        previous_stage: str | None = None
        previous_time = time.monotonic()
        report_progress = progress

        async def track_stage(message: str) -> None:
            nonlocal previous_stage, previous_time
            current = time.monotonic()
            if previous_stage is not None:
                stages[previous_stage] = round((current - previous_time) * 1000, 3)
                self.logger.debug(
                    "Backup stage completed: %s (%.3f ms)",
                    previous_stage,
                    stages[previous_stage],
                )
            previous_stage, previous_time = message, current
            if report_progress is not None:
                await report_progress(message)

        progress = track_stage
        with self.server.operations.scope(
            OperationName.BACKUP_CREATE,
            server_name=self.server.server_name,
            purpose=purpose,
        ) as operation:
            async with self.server.operation_lock:
                RestoreJournal(self.server).ensure_clear()
                await self._stage(progress, "Preparing server backup")
                use_encryption = (
                    self.server.settings.get("backups.encryption", False)
                    if encrypted is None
                    else encrypted
                )
                record = None
                if use_encryption:
                    try:
                        record = await run_in_thread(self.credentials.get)
                    except ConfigurationError:
                        if purpose != "pre_restore" or _safety_password is None:
                            raise
                        # Disaster recovery may have only the archive and its kit.
                        # Keep safety data encrypted without persisting that supplied key.
                        record = KeyRecord(
                            key_id=key_id(_safety_password),
                            secret=SecretStr(_safety_password),
                            created_at=now(),
                        )
                root = await run_in_thread(private_directory, Path(self._directory()))
                started = datetime.now(timezone.utc)
                identifier = uuid4()
                filename = (
                    started.strftime("%Y%m%dT%H%M%SZ")
                    + "_"
                    + identifier.hex
                    + ".bsmbackup"
                )
                destination = root / filename
                if _schedule_slot:
                    await run_in_thread(
                        self.catalog.update, filename, schedule_slot=_schedule_slot
                    )
                mode, chosen = selection(self.server.settings, mode, components)
                if purpose == "pre_restore" and mode != "full":
                    mode, chosen = selection(
                        self.server.settings, "selected", list(COMPONENTS[:-1])
                    )
                compression = self.server.settings.get(
                    "backups.compression", "balanced"
                )
                self.logger.info(
                    "Backup capture started: mode=%s components=%s encrypted=%s purpose=%s compression=%s",
                    mode,
                    ",".join(chosen),
                    use_encryption,
                    purpose,
                    compression,
                )
                full = mode == "full"
                server_root = Path(self.server.paths.server_dir)
                if full:
                    if await self.server.is_running():
                        raise BackupRestoreError(
                            "Stop the server before a full-directory backup."
                        )
                    if root.resolve().is_relative_to(server_root.resolve()):
                        raise BackupRestoreError(
                            "Full-directory backup storage must be outside the server directory."
                        )
                async with (
                    temporary_directory(
                        prefix=".bsm-capture-", parent=root
                    ) as directory,
                    AsyncExitStack() as capture_resources,
                ):
                    await run_in_thread(private_directory, Path(directory))
                    spool = capture_resources.enter_context(
                        CaptureSpool(Path(directory) / "captured.bin")
                    )
                    staging = Path(directory) / "contents"
                    capture_hashes: dict[Path, tuple[int, int, str]] = {}
                    await run_in_thread(private_directory, staging)
                    states: dict[Component, Literal["included", "absent"]] = {
                        name: "absent" for name in COMPONENTS
                    }
                    async with AsyncExitStack() as locks:
                        for name in sorted(
                            (
                                "server.properties",
                                "allowlist.json",
                                "permissions.json",
                                "config",
                                *PACK_COMPONENTS,
                            )
                        ):
                            await locks.enter_async_context(
                                self.server.get_file_lock(
                                    str(Path(self.server.paths.server_dir) / name)
                                )
                            )
                        capture_warnings = []
                        try:
                            world = await self.server.get_world_name()
                        except Exception:
                            if purpose != "pre_restore" and "world" in chosen:
                                raise
                            world = "unconfigured"
                            capture_warnings.append(
                                "Current properties do not identify an active world. The safety archive preserves configuration; other worlds remain on disk."
                            )
                        if _safety_world is not None:
                            if purpose != "pre_restore":
                                raise BackupRestoreError(
                                    "World overrides are reserved for restore safety captures."
                                )
                            world = _safety_world
                        safe_name(world)
                        if Path(world).name != world:
                            raise BackupRestoreError("Invalid active world name.")
                        from .space import capture_preflight

                        await self._stage(progress, "Checking backup staging space")
                        await run_in_thread(capture_preflight, self, chosen, world)
                        running = await self.server.is_running()
                        await self._stage(progress, "Capturing server files")
                        source_world = (
                            Path(self.server.paths.server_dir) / "worlds" / world
                        )
                        self._safe_target(f"worlds/{world}")
                        if root.resolve().is_relative_to(source_world.resolve()):
                            raise BackupRestoreError(
                                "Backup storage must be outside the world directory."
                            )
                        if "world" in chosen and source_world.exists():
                            # Validate the tree without following links before Bedrock's live copy.
                            if running:
                                await run_in_thread(self._check_tree, source_world)
                                await self.server.worlds._live_export_world(
                                    world, "", capture_directory=str(staging / "world")
                                )
                            else:
                                await run_in_thread(
                                    copy_source,
                                    source_world,
                                    staging / "world",
                                    hashes=capture_hashes,
                                    inherited_private=True,
                                    spool=spool,
                                )
                            states["world"] = "included"
                        elif (
                            "world" in chosen
                            and purpose != "pre_restore"
                            and source_world.parent.exists()
                            and any(source_world.parent.iterdir())
                        ):
                            raise BackupRestoreError(
                                "The active world is unexpectedly missing."
                            )
                        sources: tuple[tuple[Component, str], ...] = (
                            ("server.properties", "server.properties"),
                            ("allowlist.json", "allowlist.json"),
                            ("permissions.json", "permissions.json"),
                            ("script_config", "config"),
                            *((name, name) for name in PACK_COMPONENTS),
                        )
                        if full:
                            full_target = staging / PREFIXES["server_directory"]
                            await run_in_thread(private_directory, full_target)
                            for entry in server_entries(server_root):
                                await run_in_thread(
                                    copy_source,
                                    entry,
                                    full_target / entry.name,
                                    hashes=capture_hashes,
                                    inherited_private=True,
                                    spool=spool,
                                )
                            states["server_directory"] = "included"
                        for component, source_name in sources:
                            if component not in chosen:
                                continue
                            source = Path(self.server.paths.server_dir) / source_name
                            self._safe_target(source_name)
                            if source.is_dir() and root.resolve().is_relative_to(
                                source.resolve()
                            ):
                                raise BackupRestoreError(
                                    "Backup storage must be outside captured configuration directories."
                                )
                            if source.exists() or source.is_symlink():
                                await run_in_thread(
                                    copy_source,
                                    source,
                                    staging / PREFIXES[component],
                                    hashes=capture_hashes,
                                    inherited_private=True,
                                    spool=spool,
                                )
                                states[component] = "included"
                        if "bsm_settings" in chosen:
                            settings_path = staging / PREFIXES["bsm_settings"]
                            await run_in_thread(
                                settings_path.parent.mkdir, parents=True, exist_ok=True
                            )
                            await run_in_thread(
                                settings_path.write_text,
                                settings_export(self.server).model_dump_json(),
                                encoding="utf-8",
                            )
                            states["bsm_settings"] = "included"
                    self.logger.debug(
                        "Reusing streaming hashes from %d captured files",
                        len(capture_hashes),
                    )
                    await self._stage(progress, "Building backup inventory")
                    files, directories = await run_in_thread(
                        inventory, staging, states, hashes=capture_hashes
                    )
                    self.logger.debug(
                        "Backup inventory complete: files=%d directories=%d bytes=%d",
                        len(files),
                        len(directories),
                        sum(item.size for item in files),
                    )
                    manifest = BackupManifest(
                        backup_id=identifier,
                        created_at=started,
                        capture_started_at=started,
                        capture_finished_at=datetime.now(timezone.utc),
                        bsm_version=get_installed_version(),
                        bedrock_version=await self.server.get_version(),
                        source_server=self.server.server_name,
                        source_world=world,
                        capture_method="live" if running else "offline",
                        reason=purpose,
                        warnings=capture_warnings,
                        source_platform=platform.system(),
                        source_architecture=platform.machine(),
                        mode=mode,
                        selected_components=chosen,
                        components=states,
                        files=files,
                        directories=directories,
                    )
                    await run_in_thread(
                        check_manifest_limits,
                        manifest,
                        self.server.settings.get("backups.max_expanded_bytes", 1024**4),
                        self.server.settings.get("backups.max_files", 1_000_000),
                    )
                    temporary = Path(directory) / "snapshot"
                    password = record.secret.get_secret_value() if record else None
                    await self._stage(progress, "Compressing backup")
                    packed_payload = Path(directory) / "payload.tar.gz"
                    await run_in_thread(spool.flush)
                    await run_in_thread(
                        build_payload,
                        staging,
                        packed_payload,
                        manifest,
                        compression,
                        spool=spool,
                    )
                    await self._stage(
                        progress,
                        (
                            "Encrypting and writing archive"
                            if record
                            else "Writing archive"
                        ),
                    )
                    await run_in_thread(
                        write_archive,
                        staging,
                        temporary,
                        manifest,
                        password,
                        record.key_id if record else None,
                        prepared_payload=packed_payload,
                    )
                    if temporary.stat().st_size > self.server.settings.get(
                        "backups.max_archive_bytes", 1024**4
                    ) or packed_payload.stat().st_size > self.server.settings.get(
                        "backups.max_expanded_bytes", 1024**4
                    ):
                        raise BackupRestoreError(
                            "Backup archive exceeds configured recovery limits."
                        )
                    payload_bytes = packed_payload.stat().st_size
                    verify_created = self.server.settings.get(
                        "backups.verify_after_create", False
                    )
                    if verify_created:
                        await self._stage(progress, "Verifying backup archive")
                        verification = Path(directory) / "verify"
                        await run_in_thread(private_directory, verification)
                        await run_in_thread(
                            self.unpack_snapshot, temporary, verification, password
                        )
                    await self._stage(progress, "Validating captured contents")
                    structure_valid = True
                    try:
                        await run_in_thread(
                            self._validate_recovery_contents, staging, manifest
                        )
                    except Exception:
                        if purpose != "pre_restore":
                            raise
                        structure_valid = False
                    await self._stage(progress, "Publishing backup archive")
                    await run_in_thread(publish_archive, temporary, destination)
                await self._stage(progress, "Recording archive integrity")
                await run_in_thread(
                    self._record_verified,
                    destination,
                    manifest,
                    verified=verify_created,
                    payload_bytes=payload_bytes,
                )
                if not structure_valid:
                    await run_in_thread(
                        self.catalog.update,
                        filename,
                        verification={
                            "status": "failed",
                            "verified_at": now(),
                            "error": "Safety archive preserves damaged configuration; offline extraction may be needed.",
                        },
                    )
                if purpose == "pre_restore":
                    await run_in_thread(
                        self.catalog.update,
                        filename,
                        pinned=True,
                        protected_until=(
                            datetime.now(timezone.utc)
                            + timedelta(
                                hours=self.server.settings.get(
                                    "backups.safety_window_hours", 168
                                )
                            )
                        ).isoformat(),
                    )
                await self._stage(progress, "Copying backup destinations")
                for name, config in self.destination_configs().items():
                    if purpose != "scheduled" and config.get("enabled", True):
                        try:
                            await self.copy_snapshot(filename, name, automatic=True)
                        except BackupRestoreError:
                            self.logger.warning(
                                "Backup created locally; destination copy requires attention."
                            )
                await track_stage("Finalizing backup")
                catalog_state = await run_in_thread(self.catalog.load)
                catalog_state["archives"][filename]["stage_durations_ms"] = stages
                catalog_state["last_error"] = None
                await run_in_thread(self.catalog.save, catalog_state)
                operation.finish(
                    "completed",
                    scope=(
                        "server_snapshot",
                        f"archive:{filename}",
                        *(
                            name
                            for name, state in states.items()
                            if state == "included"
                        ),
                    ),
                )
                await self._notify_backup(filename, "capture", "completed")
                await self._stage(progress, "Applying backup retention")
                try:
                    retention = await self.prune_snapshots()
                except Exception as error:
                    log_operation_error(
                        self.logger, "Backup created but retention failed", error=error
                    )
                    from ..failures import classify_failure

                    retention = CleanupResult(
                        failures={filename: classify_failure(error).error}
                    )
                if retention.failures:
                    self.logger.warning(
                        "Backup created; retention could not remove %s archives.",
                        len(retention.failures),
                    )
                metadata = (await run_in_thread(self.catalog.load))["archives"][
                    filename
                ]
                return BackupSummary(
                    verification=metadata.get("verification", {}),
                    stage_durations_ms=metadata.get("stage_durations_ms", {}),
                    pinned=metadata.get("pinned", False),
                    protected_until=metadata.get("protected_until"),
                    purpose=purpose,
                    copies=metadata.get("copies", {}),
                    backup_id=filename,
                    filename=filename,
                    size=destination.stat().st_size,
                    encrypted=bool(record),
                    key_id=record.key_id if record else None,
                    manifest=manifest,
                    error=(
                        "Retention could not remove some older backups."
                        if retention.failures
                        else None
                    ),
                )

    @staticmethod
    def _check_tree(source: Path, cancellation_event=None) -> None:
        check_cancellation(cancellation_event)
        if is_link(source):
            raise BackupRestoreError("Backup sources must not contain symbolic links.")
        safe_name(source.name)
        if source.is_dir():
            for child in source.iterdir():
                UnifiedServerBackups._check_tree(child, cancellation_event)
        elif not source.is_file():
            raise BackupRestoreError("Backup sources must be regular files.")

    async def can_reuse_sequence_snapshot(self, *, mode=None, components=None) -> bool:
        """Require a complete capture covering every component currently present."""
        from ..events.operations import OperationResultQuery

        async with self.server.operation_lock:
            _, chosen = selection(self.server.settings, mode, components)
            required = set(chosen) & {"bsm_settings", "server_directory"}
            try:
                world = await self.server.get_world_name()
                sources = {
                    "world": f"worlds/{world}",
                    "server.properties": "server.properties",
                    "allowlist.json": "allowlist.json",
                    "permissions.json": "permissions.json",
                    "script_config": "config",
                }
                if any(c in chosen for c in PACK_COMPONENTS):
                    sources.update({name: name for name in PACK_COMPONENTS})
                for component, name in sources.items():
                    target = self._safe_target(name)
                    if component in chosen and target.exists():
                        if is_link(target):
                            return False
                        required.add(component)
            except Exception:
                return False
            metadata = (await run_in_thread(self.catalog.load))["archives"]
            for item in self.server.operations.results(
                OperationResultQuery(
                    name=OperationName.BACKUP_CREATE,
                    server_name=self.server.server_name,
                    status="finished",
                    outcome="completed",
                )
            ):
                if "server_snapshot" not in item.scope or not (
                    required.issubset(item.scope)
                    or (
                        "server_directory" in item.scope
                        and "server_directory" not in required
                        and (
                            "bsm_settings" not in required
                            or "bsm_settings" in item.scope
                        )
                    )
                ):
                    continue
                for marker in item.scope:
                    if not marker.startswith("archive:"):
                        continue
                    identifier = marker.removeprefix("archive:")
                    try:
                        path = self.resolve_backup(identifier)
                        record = metadata.get(identifier, {})
                        current = await run_in_thread(path.stat)
                        verified = record.get("verification", {}).get("status")
                        if (
                            verified == "verified"
                            or (
                                record.get("capture_validated", False)
                                and verified != "failed"
                            )
                        ) and record.get("fingerprint") == [
                            current.st_size,
                            current.st_mtime_ns,
                        ]:
                            return True
                    except (BackupRestoreError, OSError):
                        continue
            return False

    async def backup_all_data(
        self,
        *,
        purpose: Literal["manual", "pre_start", "pre_update"] = "manual",
        mode=None,
        components=None,
        encrypted=None,
    ) -> ComponentResults:
        snapshot = await self.create_snapshot(
            purpose=purpose, mode=mode, components=components, encrypted=encrypted
        )
        assert snapshot.manifest is not None
        return ComponentResults(
            components={
                name: (
                    CompletedItem(
                        outcome="completed",
                        path=str(Path(self._directory()) / snapshot.filename),
                    )
                    if state == "included"
                    else SkippedItem(outcome="skipped", reason="Source is absent.")
                )
                for name, state in snapshot.manifest.components.items()
            }
        )

    async def inspect_snapshot(
        self, identifier: str, recovery_key: str | None = None
    ) -> BackupSummary:
        async with self.server.operation_lock:
            path = self.resolve_backup(identifier)
            password = await run_in_thread(self._password, path, recovery_key)
            async with temporary_directory(
                prefix=".bsm-inspect-", parent=path.parent
            ) as directory:
                manifest = await backup_worker(
                    self.unpack_snapshot,
                    path,
                    Path(directory),
                    password,
                    materialize=False,
                )
            info = await run_in_thread(header, path)
            return BackupSummary(
                backup_id=identifier,
                filename=identifier,
                size=path.stat().st_size,
                encrypted=info.encrypted,
                key_id=info.key_id,
                manifest=manifest,
            )

    async def list_snapshots(self) -> list[BackupSummary]:
        root = Path(self._directory())

        def scan():
            if not root.exists():
                return []
            entries = []
            for path in sorted(root.glob("*.bsmbackup"), reverse=True):
                if path.is_symlink() or not path.is_file():
                    continue
                try:
                    entries.append((path, path.stat()))
                except FileNotFoundError:
                    continue
            return entries

        result = []
        catalog = await run_in_thread(self.catalog.load)
        for path, metadata_stat in await run_in_thread(scan):
            metadata = dict(catalog["archives"].get(path.name, {}))
            if metadata.get("fingerprint") != [
                metadata_stat.st_size,
                metadata_stat.st_mtime_ns,
            ]:
                metadata.pop("verification", None)
            drill = metadata.get("drill")
            if (
                drill
                and drill.get("status") == "passed"
                and drill.get("fingerprint")
                != [
                    metadata_stat.st_size,
                    metadata_stat.st_mtime_ns,
                ]
            ):
                metadata.pop("drill", None)
            try:
                info = await run_in_thread(header, path)
                result.append(
                    BackupSummary(
                        backup_id=path.name,
                        filename=path.name,
                        created_at=metadata.get("created_at"),
                        drill=metadata.get("drill"),
                        size=metadata_stat.st_size,
                        verification=metadata.get("verification", {}),
                        stage_durations_ms=metadata.get("stage_durations_ms", {}),
                        pinned=metadata.get("pinned", False),
                        protected_until=metadata.get("protected_until"),
                        purpose=metadata.get("purpose"),
                        copies=metadata.get("copies", {}),
                        label=metadata.get("label", ""),
                        notes=metadata.get("notes", ""),
                        origin=metadata.get("origin", "captured"),
                        encrypted=info.encrypted,
                        key_id=info.key_id,
                        error=metadata.get("metadata_error"),
                    )
                )
            except BackupRestoreError:
                result.append(
                    BackupSummary(
                        backup_id=path.name,
                        filename=path.name,
                        created_at=metadata.get("created_at"),
                        drill=metadata.get("drill"),
                        size=metadata_stat.st_size,
                        encrypted=False,
                        verification=metadata.get("verification", {}),
                        stage_durations_ms=metadata.get("stage_durations_ms", {}),
                        pinned=metadata.get("pinned", False),
                        protected_until=metadata.get("protected_until"),
                        purpose=metadata.get("purpose"),
                        copies=metadata.get("copies", {}),
                        label=metadata.get("label", ""),
                        notes=metadata.get("notes", ""),
                        origin=metadata.get("origin", "captured"),
                        error="Invalid backup header.",
                    )
                )
        return result

    async def prune_snapshots(self) -> CleanupResult:
        return await self.prune_managed_snapshots()

    def _destinations(
        self, staging: Path, manifest: BackupManifest, components: list[Component]
    ) -> tuple[dict[Component, str], list[str]]:
        try:
            return self._validated_destinations(staging, manifest, components)
        except BackupRestoreError:
            raise
        except Exception as error:
            raise BackupRestoreError(
                "Selected configuration is invalid or cannot be read."
            ) from error

    def _validated_destinations(
        self, staging: Path, manifest: BackupManifest, components: list[Component]
    ) -> tuple[dict[Component, str], list[str]]:
        if (
            not components
            or len(set(components)) != len(components)
            or any(
                c not in COMPONENTS or manifest.components.get(c) != "included"
                for c in components
            )
        ):
            raise BackupRestoreError(
                "Select available backup components without duplicates."
            )
        if "bsm_settings" in components:
            exported = ServerSettingsExport.model_validate_json(
                (staging / PREFIXES["bsm_settings"]).read_bytes()
            )
            validator = getattr(self.server.storage, "custom_settings_validator", None)
            if validator is not None:
                validator(
                    "server",
                    self.server.configuration.snapshot().custom,
                    exported.custom,
                    self.server.server_name,
                )
        if "server_directory" in components:
            if (manifest.source_platform, manifest.source_architecture) != (
                platform.system(),
                platform.machine(),
            ):
                raise BackupRestoreError(
                    "Full-directory restore requires the same operating system and architecture."
                )
            if any(c not in ("server_directory", "bsm_settings") for c in components):
                raise BackupRestoreError(
                    "Full-directory restore cannot be combined with individual file components."
                )
            if (
                manifest.bedrock_version
                != self.server.configuration.snapshot().installed_version
            ):
                raise BackupRestoreError(
                    "Full-directory restore requires the same installed Bedrock version."
                )
            return {
                c: ("." if c == "server_directory" else "BSM server settings")
                for c in components
            }, [
                *manifest.warnings,
                "Full-directory restore replaces all server files and worlds. The server must be stopped.",
            ]
        properties = (
            staging / PREFIXES["server.properties"]
            if "server.properties" in components
            else Path(self.server.paths.server_properties_path)
        )
        world = (
            self._read_world(properties)
            if "world" in components or "server.properties" in components
            else manifest.source_world
        )
        if manifest.reason == "pre_restore" and "world" in components:
            world = manifest.source_world
            if Path(safe_name(world)).name != world:
                raise BackupRestoreError("Invalid safety world destination.")
        warnings = list(manifest.warnings)
        if manifest.source_server != self.server.server_name:
            warnings.append(
                "This backup came from a different server. The destination identity will be preserved."
            )
        if (
            manifest.bedrock_version
            != self.server.configuration.snapshot().installed_version
        ):
            warnings.append(
                "Bedrock versions differ. BSM will not install or downgrade the executable."
            )
        if (
            "world" not in components
            and "server.properties" in components
            and not (Path(self.server.paths.server_dir) / "worlds" / world).is_dir()
        ):
            if manifest.components["world"] == "included":
                raise BackupRestoreError(
                    "Restored properties would select a missing world. Include the world component."
                )
            warnings.append(
                "This backup contains no generated world. Bedrock may generate one at next start."
            )
        if "world" in components and "server.properties" not in components:
            warnings.append(
                "The backup world will replace the destination's current active world."
            )
        if "script_config" in components:
            warnings.append(
                "Script configuration replaces the complete config directory, including secrets and module permissions."
            )
        if any(
            component in components
            for component in ("permissions.json", "allowlist.json", "bsm_settings")
        ):
            warnings.append(
                "Selected settings may change player access, operator permissions, automatic startup, or custom secrets. Sensitive values are hidden in this review."
            )
        targets: dict[Component, str] = {}
        for component in components:
            targets[component] = (
                f"worlds/{world}"
                if component == "world"
                else (
                    "config"
                    if component == "script_config"
                    else (
                        "BSM server settings"
                        if component == "bsm_settings"
                        else component
                    )
                )
            )
            if component != "bsm_settings":
                self._safe_target(targets[component])
        for component in ("allowlist.json", "permissions.json"):
            if component in components:
                if not isinstance(
                    json.loads((staging / PREFIXES[component]).read_bytes()), list
                ):
                    raise BackupRestoreError("Invalid player access configuration.")
        if "bsm_settings" in components:
            ServerSettingsExport.model_validate_json(
                (staging / PREFIXES["bsm_settings"]).read_bytes()
            )
        if "world" in components and not any(
            (staging / "world" / name).is_file() for name in ("level.dat", "level.txt")
        ):
            raise BackupRestoreError("Backup world metadata is missing.")
        return targets, warnings

    @staticmethod
    def _read_world(properties: Path) -> str:
        world = None
        for line in properties.read_text(encoding="utf-8-sig").splitlines():
            if line.strip().startswith("level-name="):
                world = line.strip().partition("=")[2].strip()
        if not world or Path(safe_name(world)).name != world:
            raise BackupRestoreError("Properties do not identify a valid world.")
        return world

    def _component_target(self, component, name):
        if component == "server_directory" and name == ".":
            return Path(self.server.paths.server_dir).resolve()
        return self._safe_target(name)

    def _comparison_paths(self, component, target, cancellation_event=None):
        if component == "server_directory":
            paths = []
            for entry in server_entries(target):
                self._check_tree(entry, cancellation_event)
                paths.extend(sorted(tree_paths(entry, cancellation_event)))
            return paths
        self._check_tree(target, cancellation_event) if target.exists() else None
        return sorted(tree_paths(target, cancellation_event))

    def _safe_target(self, name: str) -> Path:
        safe_name(name)
        root = Path(self.server.paths.server_dir).resolve()
        target = root / name
        if target.resolve() != target or any(
            parent.is_symlink()
            for parent in (Path(self.server.paths.server_dir), *target.parents)
            if parent != root.parent
        ):
            raise BackupRestoreError("Restore destination contains a symbolic link.")
        return target

    def _plan_token(
        self,
        path: Path,
        targets: dict[Component, str],
        cancellation_event=None,
        *,
        hashes=None,
    ) -> tuple[str, int]:
        check_cancellation(cancellation_event)
        state = {
            "archive": digest(path, cancellation_event),
            "targets": targets,
            "installed_version": self.server.configuration.snapshot().installed_version,
            "settings": settings_export(self.server).model_dump(mode="json"),
        }

        def checksum(source):
            value = digest(source, cancellation_event)
            if hashes is not None:
                metadata = source.stat()
                hashes[source] = (metadata.st_size, metadata.st_mtime_ns, value)
            return value

        fingerprints = {}
        recovery_size = 0
        for component, name in targets.items():
            check_cancellation(cancellation_event)
            if component == "bsm_settings":
                continue
            target = self._component_target(component, name)
            paths = self._comparison_paths(component, target, cancellation_event)
            recovery_size += sum(p.stat().st_size for p in paths if p.is_file())
            # World contents naturally change while running; bind its destination identity instead.
            fingerprints[component] = (
                [
                    (
                        str(p.relative_to(target.parent)),
                        checksum(p),
                        p.stat().st_mode & 0o100,
                    )
                    for p in paths
                    if p.is_file()
                ]
                if component != "world"
                else target.exists()
            )
        state["files"] = fingerprints
        return (
            hashlib.sha256(json.dumps(state, sort_keys=True).encode()).hexdigest(),
            recovery_size,
        )

    async def plan_restore(
        self,
        identifier: str,
        components: list[Component],
        recovery_key: str | None = None,
        *,
        dry_run: bool = False,
        _all_components: bool = False,
    ) -> RestorePlan:
        async with self.server.operation_lock:
            RestoreJournal(self.server).ensure_clear()
            if "server_directory" in components and await self.server.is_running():
                raise BackupRestoreError(
                    "Stop the server before reviewing a full-directory restore."
                )
            path = await run_in_thread(self.resolve_backup, identifier)
            password = await run_in_thread(self._password, path, recovery_key)
            from .space import existing_parent, restore_capacity

            target_root = Path(self.server.paths.server_dir)
            if dry_run:
                await report_stage("Testing isolated restore extraction")
            async with temporary_directory(
                prefix=".bsm-dry-run-" if dry_run else ".bsm-plan-",
                parent=existing_parent(target_root) if dry_run else path.parent,
            ) as directory:
                staging = Path(directory)
                manifest = await backup_worker(
                    self.unpack_snapshot, path, staging, password, durable=dry_run
                )
                if _all_components:
                    components = [
                        name
                        for name, state in manifest.components.items()
                        if state == "included"
                    ]
                if "server_directory" in components and await self.server.is_running():
                    raise BackupRestoreError(
                        "Stop the server before reviewing a full-directory restore."
                    )
                targets, warnings = await run_in_thread(
                    self._destinations, staging, manifest, components
                )
                await report_stage("Checking restore destinations")
                current_hashes: dict[Path, tuple[int, int, str]] = {}
                token, old_bytes = await backup_worker(
                    self._plan_token, path, targets, hashes=current_hashes
                )
                volumes = await run_in_thread(restore_capacity, self, manifest, targets)
                checked = 0
                if dry_run and all(volume.sufficient for volume in volumes):
                    # Materialize once on the destination filesystem, then read it back.
                    await report_stage("Checking staged restore checksums")
                    checked = await backup_worker(
                        verify_staging, staging, manifest, components
                    )
                await report_stage("Comparing restore contents")
                changes, counts, settings = await backup_worker(
                    self.restore_comparison,
                    staging,
                    targets,
                    manifest=manifest,
                    hashes=current_hashes,
                )
                plan = RestorePlan(
                    backup_id=identifier,
                    token=token,
                    components=components,
                    destinations=targets,
                    warnings=warnings,
                    required_bytes=sum(v.required_bytes for v in volumes),
                    volumes=volumes,
                    sufficient_space=all(v.sufficient for v in volumes),
                    dry_run=dry_run,
                    checked_files=checked,
                    changes=changes,
                    change_counts=counts,
                    setting_changes=settings,
                    changes_truncated=sum(counts.values()) > len(changes),
                )
                from .reports import record_review

                await run_in_thread(record_review, self, plan)
                return plan

    async def restore_snapshot(
        self,
        identifier: str,
        components: list[Component],
        token: str,
        recovery_key: str | None = None,
        *,
        stop_server=None,
        start_server=None,
        restart: bool = True,
        progress=None,
    ) -> RestoreResult:
        if self.server.state is None:
            raise BackupRestoreError("Server state is unavailable.")
        async with self.server.operation_lock:
            with self.server.state.servers.maintenance(self.server.server_name).hold():
                from .reports import record_outcome

                try:
                    result = await self._restore_snapshot(
                        identifier,
                        components,
                        token,
                        recovery_key,
                        stop_server=stop_server,
                        start_server=start_server,
                        restart=restart,
                        progress=progress,
                    )
                except BaseException as error:
                    await record_outcome(self, identifier, components, error=error)
                    raise
                await record_outcome(self, identifier, components, result=result)
                return result

    async def _restore_snapshot(
        self,
        identifier: str,
        components: list[Component],
        token: str,
        recovery_key: str | None = None,
        *,
        stop_server=None,
        start_server=None,
        restart: bool = True,
        progress: Callable[[str], Awaitable[None]] | None = None,
    ) -> RestoreResult:
        async with self.server.operation_lock:
            await self._stage(progress, "Validating selected backup")
            journal = RestoreJournal(self.server)
            journal.ensure_clear()
            path = self.resolve_backup(identifier)
            password = await run_in_thread(self._password, path, recovery_key)
            root = Path(self.server.paths.server_dir)
            await run_in_thread(root.mkdir, parents=True, exist_ok=True)
            async with temporary_directory(
                prefix=".bsm-restore-stage-", parent=root
            ) as directory:
                staging = Path(directory)
                manifest = await backup_worker(
                    self.unpack_snapshot, path, staging, password, durable=True
                )
                targets, _ = await run_in_thread(
                    self._destinations, staging, manifest, components
                )
                current, old_bytes = await backup_worker(
                    self._plan_token, path, targets
                )
                if current != token:
                    raise BackupRestoreError(
                        "Restore plan is stale. Review a new plan before restoring."
                    )
                from .space import restore_capacity

                capacity = await run_in_thread(
                    restore_capacity, self, manifest, targets, staged=True
                )
                if not all(volume.sufficient for volume in capacity):
                    raise BackupRestoreError(
                        "Insufficient space on the server or backup volume for staging and a safety archive."
                    )
                was_running = await self.server.is_running()
                await self._stage(progress, "Preparing restore recovery")
                if was_running:
                    if stop_server is None:
                        raise BackupRestoreError("Stop the server before restoring.")
                    await self._stage(progress, "Stopping Minecraft server")
                    await stop_server()
                    if await self.server.is_running():
                        raise BackupRestoreError("The server did not stop.")
                await run_in_thread(
                    self.catalog.update,
                    identifier,
                    protected_until=(
                        datetime.now(timezone.utc)
                        + timedelta(
                            hours=self.server.settings.get(
                                "backups.safety_window_hours", 168
                            )
                        )
                    ).isoformat(),
                )
                await self._stage(
                    progress, "Creating protected pre-restore safety backup"
                )
                safety = await self.create_snapshot(
                    purpose="pre_restore",
                    mode="full" if "server_directory" in targets else "selected",
                    _safety_password=password if header(path).encrypted else None,
                    _safety_world=(
                        Path(targets["world"]).name if "world" in targets else None
                    ),
                    encrypted=header(path).encrypted
                    or self.server.settings.get("backups.encryption", False),
                )
                # Safety capture is independent from the recovery journal and survives a successful restore.
                async with AsyncExitStack() as locks:
                    full = "server_directory" in targets
                    if full:
                        full_source = staging / PREFIXES["server_directory"]
                        entries = {p.name for p in server_entries(root)} | {
                            p.name for p in server_entries(full_source)
                        }
                        replacements = [
                            (
                                name,
                                (
                                    full_source / name
                                    if (full_source / name).exists()
                                    else None
                                ),
                            )
                            for name in sorted(entries)
                        ]
                    else:
                        replacements = [
                            (target, staging / PREFIXES[c])
                            for c, target in targets.items()
                            if c != "bsm_settings"
                        ]
                    for name, _ in replacements:
                        self._safe_target(name)
                        await locks.enter_async_context(
                            self.server.get_file_lock(str(root / name))
                        )
                    await run_in_thread(
                        journal.begin,
                        [name for name, _ in replacements],
                        "bsm_settings" in components,
                        full,
                    )
                    try:
                        await self._stage(progress, "Restoring selected components")
                        for index, (_, source) in enumerate(replacements):
                            await run_in_thread(journal.replace, index, source)
                        if "bsm_settings" in components:
                            exported = ServerSettingsExport.model_validate_json(
                                (staging / PREFIXES["bsm_settings"]).read_bytes()
                            )
                            await apply_settings(
                                self.server, exported, commit=journal.commit
                            )
                        else:
                            await run_in_thread(journal.commit)
                    except BaseException as error:
                        import asyncio

                        committed = (
                            journal.record.exists()
                            and (await run_in_thread(journal._load))["committed"]
                        )
                        recovery = asyncio.create_task(journal.recover())
                        try:
                            while not recovery.done():
                                try:
                                    await asyncio.shield(recovery)
                                except asyncio.CancelledError:
                                    continue
                            recovery.result()
                        except Exception as recovery_error:
                            log_operation_error(
                                self.logger,
                                "Restore recovery failed",
                                error=recovery_error,
                            )
                            if committed:
                                return RestoreResult(
                                    restored=components,
                                    cleanup_warning="Restore committed; recovery journal cleanup requires attention. The server remains stopped.",
                                )
                            raise BackupRestoreError(
                                "Restore failed and recovery is incomplete. The server remains stopped; retain its recovery journal."
                            ) from error
                        if committed:
                            return RestoreResult(
                                restored=components,
                                cleanup_warning="Restore committed before completion was interrupted. The server remains stopped.",
                            )
                        raise
                cleanup_warning = None
                try:
                    await run_in_thread(
                        self.catalog.update,
                        safety.backup_id,
                        pinned=safety.verification.status == "failed",
                        protected_until=(
                            datetime.now(timezone.utc)
                            + timedelta(
                                hours=self.server.settings.get(
                                    "backups.safety_window_hours", 168
                                )
                            )
                        ).isoformat(),
                    )
                except Exception as error:
                    log_operation_error(
                        self.logger,
                        "Restore safety metadata update failed",
                        error=error,
                    )
                    cleanup_warning = "Data restored; safety archive protection metadata needs attention. Its pin remains in place."
                try:
                    await run_in_thread(shutil.rmtree, journal.path)
                except OSError as error:
                    log_operation_error(
                        self.logger, "Restore journal cleanup failed", error=error
                    )
                    cleanup_warning = "Restore committed; recovery journal cleanup will be retried at startup."
                restarted = False
                restart_error = None
                if was_running and restart and start_server is not None:
                    await self._stage(progress, "Starting Minecraft server")
                    try:
                        await start_server()
                        restarted = await self.server.is_running()
                        if not restarted:
                            restart_error = "Server start was skipped or cancelled."
                    except Exception as error:
                        log_operation_error(
                            self.logger,
                            "Restore completed but restart failed",
                            error=error,
                        )
                        restart_error = "Data restored successfully, but the server could not restart."
                return RestoreResult(
                    restored=components,
                    safety_backup_id=safety.backup_id,
                    restarted=restarted,
                    restart_error=restart_error,
                    cleanup_warning=cleanup_warning,
                )
