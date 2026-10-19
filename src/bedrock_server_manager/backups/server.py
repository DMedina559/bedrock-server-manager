"""Unified server snapshots with selective restore and persistent recovery."""

import hashlib
import json
import logging
import os
import shutil
import stat
import tempfile
from contextlib import AsyncExitStack
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Awaitable, Callable, Literal
from uuid import uuid4

from ..config.const import get_installed_version
from ..error import BackupRestoreError, ConfigurationError
from ..operations import OperationName
from ..results import CleanupResult, CompletedItem, ComponentResults, SkippedItem
from ..utils.threads import run_in_thread
from .archive import digest, header, safe_name, unpack, write_archive
from .catalog import ManagedBackups, now
from .credentials import BackupCredentials, private_directory, protect
from .models import (
    COMPONENTS,
    PREFIXES,
    BackupFile,
    BackupManifest,
    BackupSummary,
    Component,
    RestorePlan,
    RestoreRecoveryState,
    RestoreResult,
    ServerSettingsExport,
)
from .recovery import RestoreJournal, apply_settings, settings_export, sync_tree

if TYPE_CHECKING:
    from ..core.bedrock_server import BedrockServer


def is_link(source: Path) -> bool:
    return source.is_symlink() or bool(
        getattr(source.lstat(), "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    )


def copy_source(source: Path, target: Path) -> None:
    """Copy only portable regular files and directories, never following links."""
    safe_name(source.name)
    if is_link(source):
        raise BackupRestoreError("Backup sources must not contain symbolic links.")
    if source.is_dir():
        target.mkdir(parents=True, exist_ok=True)
        for child in source.iterdir():
            copy_source(child, target / child.name)
    elif source.is_file():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        protect(target)
    else:
        raise BackupRestoreError("Backup source is not a regular file or directory.")


def inventory(staging: Path, components) -> tuple[list[BackupFile], list[str]]:
    files = []
    directories = []
    for component, state in components.items():
        if state != "included":
            continue
        root = staging / PREFIXES[component]
        paths = [root, *sorted(root.rglob("*"))] if root.is_dir() else [root]
        for path in paths:
            name = safe_name(path.relative_to(staging).as_posix())
            if path.is_dir():
                directories.append(name)
            else:
                files.append(
                    BackupFile(
                        path=name,
                        component=component,
                        size=path.stat().st_size,
                        sha256=digest(path),
                    )
                )
    return files, directories


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
        self, path: Path, destination: Path, password: str | None = None
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

    @staticmethod
    async def _stage(progress, message: str) -> None:
        if progress is not None:
            await progress(message)

    async def create_snapshot(
        self,
        *,
        encrypted: bool | None = None,
        purpose: Literal["manual", "pre_start", "pre_update", "pre_restore"] = "manual",
        progress: Callable[[str], Awaitable[None]] | None = None,
        _safety_world: str | None = None,
    ) -> BackupSummary:
        try:
            return await self._create_snapshot(
                encrypted=encrypted,
                purpose=purpose,
                progress=progress,
                _safety_world=_safety_world,
            )
        except Exception:
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
        purpose: Literal["manual", "pre_start", "pre_update", "pre_restore"] = "manual",
        progress: Callable[[str], Awaitable[None]] | None = None,
        _safety_world: str | None = None,
    ) -> BackupSummary:
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
                record = (
                    await run_in_thread(self.credentials.get)
                    if use_encryption
                    else None
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
                with tempfile.TemporaryDirectory(
                    prefix=".bsm-capture-", dir=root
                ) as directory:
                    staging = Path(directory) / "contents"
                    await run_in_thread(private_directory, staging)
                    components: dict[Component, Literal["included", "absent"]] = {
                        name: "absent" for name in COMPONENTS
                    }
                    async with AsyncExitStack() as locks:
                        for name in sorted(
                            (
                                "server.properties",
                                "allowlist.json",
                                "permissions.json",
                                "config",
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
                            if purpose != "pre_restore":
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
                        if source_world.exists():
                            # Validate the tree without following links before Bedrock's live copy.
                            if running:
                                await run_in_thread(self._check_tree, source_world)
                                await self.server.worlds._live_export_world(
                                    world, "", capture_directory=str(staging / "world")
                                )
                            else:
                                await run_in_thread(
                                    copy_source, source_world, staging / "world"
                                )
                            components["world"] = "included"
                        elif (
                            purpose != "pre_restore"
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
                        )
                        for component, source_name in sources:
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
                                    copy_source, source, staging / PREFIXES[component]
                                )
                                components[component] = "included"
                        settings_path = staging / PREFIXES["bsm_settings"]
                        await run_in_thread(
                            settings_path.parent.mkdir, parents=True, exist_ok=True
                        )
                        await run_in_thread(
                            settings_path.write_text,
                            settings_export(self.server).model_dump_json(),
                            encoding="utf-8",
                        )
                        components["bsm_settings"] = "included"
                    await self._stage(progress, "Building backup inventory")
                    files, directories = await run_in_thread(
                        inventory, staging, components
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
                        warnings=capture_warnings
                        + (
                            [
                                "Server-level packs outside the active world are not included; preserve them separately."
                            ]
                            if any(
                                (Path(self.server.paths.server_dir) / name).is_dir()
                                and any(
                                    (
                                        Path(self.server.paths.server_dir) / name
                                    ).iterdir()
                                )
                                for name in (
                                    "behavior_packs",
                                    "resource_packs",
                                    "development_behavior_packs",
                                    "development_resource_packs",
                                )
                            )
                            else []
                        ),
                        components=components,
                        files=files,
                        directories=directories,
                    )
                    temporary = Path(directory) / "snapshot"
                    password = record.secret.get_secret_value() if record else None
                    await self._stage(
                        progress,
                        (
                            "Compressing and encrypting backup"
                            if record
                            else "Compressing backup"
                        ),
                    )
                    await run_in_thread(
                        write_archive,
                        staging,
                        temporary,
                        manifest,
                        password,
                        record.key_id if record else None,
                    )
                    verification = Path(directory) / "verify"
                    await run_in_thread(private_directory, verification)
                    await run_in_thread(
                        self.unpack_snapshot, temporary, verification, password
                    )
                    structure_valid = True
                    try:
                        await run_in_thread(
                            self._validate_recovery_contents, staging, manifest
                        )
                    except Exception:
                        if purpose != "pre_restore":
                            raise
                        structure_valid = False
                    await run_in_thread(sync_tree, temporary)
                    await run_in_thread(os.replace, temporary, destination)
                await run_in_thread(self._record_verified, destination, manifest)
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
                for name, config in self.destination_configs().items():
                    if config.get("enabled", True):
                        try:
                            await self.copy_snapshot(filename, name)
                        except BackupRestoreError:
                            self.logger.warning(
                                "Backup created locally; destination copy requires attention."
                            )
                catalog_state = await run_in_thread(self.catalog.load)
                catalog_state["last_error"] = None
                await run_in_thread(self.catalog.save, catalog_state)
                operation.finish(
                    "completed",
                    scope=tuple(
                        name
                        for name, state in components.items()
                        if state == "included"
                    ),
                )
                await self._notify_backup(filename, "capture", "completed")
                retention = await self.prune_snapshots()
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
    def _check_tree(source: Path) -> None:
        if is_link(source):
            raise BackupRestoreError("Backup sources must not contain symbolic links.")
        safe_name(source.name)
        if source.is_dir():
            for child in source.iterdir():
                UnifiedServerBackups._check_tree(child)
        elif not source.is_file():
            raise BackupRestoreError("Backup sources must be regular files.")

    async def backup_all_data(
        self, *, purpose: Literal["manual", "pre_start", "pre_update"] = "manual"
    ) -> ComponentResults:
        snapshot = await self.create_snapshot(purpose=purpose)
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
            with tempfile.TemporaryDirectory(
                prefix=".bsm-inspect-", dir=path.parent
            ) as directory:
                manifest = await run_in_thread(
                    self.unpack_snapshot, path, Path(directory), password
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
        async with self.server.operation_lock:
            root = Path(self._directory())
            if not root.exists():
                return []
            result = []
            catalog = await run_in_thread(self.catalog.load)
            for path in sorted(root.glob("*.bsmbackup"), reverse=True):
                if path.is_symlink() or not path.is_file():
                    continue
                metadata = dict(catalog["archives"].get(path.name, {}))
                if metadata.get("fingerprint") != [
                    path.stat().st_size,
                    path.stat().st_mtime_ns,
                ]:
                    metadata.pop("verification", None)
                try:
                    info = await run_in_thread(header, path)
                    result.append(
                        BackupSummary(
                            backup_id=path.name,
                            filename=path.name,
                            size=path.stat().st_size,
                            verification=metadata.get("verification", {}),
                            pinned=metadata.get("pinned", False),
                            protected_until=metadata.get("protected_until"),
                            purpose=metadata.get("purpose"),
                            copies=metadata.get("copies", {}),
                            encrypted=info.encrypted,
                            key_id=info.key_id,
                        )
                    )
                except BackupRestoreError:
                    result.append(
                        BackupSummary(
                            backup_id=path.name,
                            filename=path.name,
                            size=path.stat().st_size,
                            encrypted=False,
                            verification=metadata.get("verification", {}),
                            pinned=metadata.get("pinned", False),
                            protected_until=metadata.get("protected_until"),
                            purpose=metadata.get("purpose"),
                            copies=metadata.get("copies", {}),
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
        except Exception:
            raise BackupRestoreError(
                "Selected configuration is invalid or cannot be read."
            ) from None

    def _validated_destinations(
        self, staging: Path, manifest: BackupManifest, components: list[Component]
    ) -> tuple[dict[Component, str], list[str]]:
        if (
            not components
            or len(set(components)) != len(components)
            or any(
                c not in COMPONENTS or manifest.components[c] != "included"
                for c in components
            )
        ):
            raise BackupRestoreError(
                "Select available backup components without duplicates."
            )
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

    def _plan_token(self, path: Path, targets: dict[Component, str]) -> tuple[str, int]:
        state = {
            "archive": digest(path),
            "targets": targets,
            "installed_version": self.server.configuration.snapshot().installed_version,
            "settings": settings_export(self.server).model_dump(mode="json"),
        }
        fingerprints = {}
        recovery_size = 0
        for component, name in targets.items():
            if component == "bsm_settings":
                continue
            target = self._safe_target(name)
            paths = (
                [target, *sorted(target.rglob("*"))] if target.is_dir() else [target]
            )
            self._check_tree(target) if target.exists() else None
            recovery_size += sum(p.stat().st_size for p in paths if p.is_file())
            # World contents naturally change while running; bind its destination identity instead.
            fingerprints[component] = (
                [
                    (str(p.relative_to(target.parent)), digest(p))
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
    ) -> RestorePlan:
        async with self.server.operation_lock:
            RestoreJournal(self.server).ensure_clear()
            path = self.resolve_backup(identifier)
            password = await run_in_thread(self._password, path, recovery_key)
            with tempfile.TemporaryDirectory(
                prefix=".bsm-plan-", dir=path.parent
            ) as directory:
                staging = Path(directory)
                manifest = await run_in_thread(
                    self.unpack_snapshot, path, staging, password
                )
                targets, warnings = await run_in_thread(
                    self._destinations, staging, manifest, components
                )
                token, old_bytes = await run_in_thread(self._plan_token, path, targets)
                size = sum(item.size for item in manifest.files) + old_bytes
                changes, counts, settings = await run_in_thread(
                    self.restore_comparison, staging, targets
                )
                return RestorePlan(
                    backup_id=identifier,
                    token=token,
                    components=components,
                    destinations=targets,
                    warnings=warnings,
                    required_bytes=size * 2,
                    changes=changes,
                    change_counts=counts,
                    setting_changes=settings,
                    changes_truncated=sum(counts.values()) > len(changes),
                )

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
                return await self._restore_snapshot(
                    identifier,
                    components,
                    token,
                    recovery_key,
                    stop_server=stop_server,
                    start_server=start_server,
                    restart=restart,
                    progress=progress,
                )

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
            with tempfile.TemporaryDirectory(
                prefix=".bsm-restore-stage-", dir=root
            ) as directory:
                staging = Path(directory)
                manifest = await run_in_thread(
                    self.unpack_snapshot, path, staging, password
                )
                targets, _ = await run_in_thread(
                    self._destinations, staging, manifest, components
                )
                current, old_bytes = await run_in_thread(
                    self._plan_token, path, targets
                )
                if current != token:
                    raise BackupRestoreError(
                        "Restore plan is stale. Review a new plan before restoring."
                    )
                if shutil.disk_usage(root.parent).free < old_bytes + sum(
                    item.size for item in manifest.files
                ):
                    raise BackupRestoreError("Insufficient space for restore recovery.")
                await run_in_thread(sync_tree, staging)
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
                    _safety_world=(
                        Path(targets["world"]).name if "world" in targets else None
                    ),
                    encrypted=header(path).encrypted
                    or self.server.settings.get("backups.encryption", False),
                )
                # Safety capture is independent from the recovery journal and survives a successful restore.
                async with AsyncExitStack() as locks:
                    for name in sorted(
                        target
                        for component, target in targets.items()
                        if component != "bsm_settings"
                    ):
                        await locks.enter_async_context(
                            self.server.get_file_lock(str(root / name))
                        )
                    file_components = [c for c in components if c != "bsm_settings"]
                    await run_in_thread(
                        journal.begin,
                        [targets[c] for c in file_components],
                        "bsm_settings" in components,
                    )
                    try:
                        await self._stage(progress, "Restoring selected components")
                        for index, component in enumerate(file_components):
                            await run_in_thread(
                                journal.replace, index, staging / PREFIXES[component]
                            )
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
                        except Exception:
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
                        pinned=safety.verification.status != "verified",
                        protected_until=(
                            datetime.now(timezone.utc)
                            + timedelta(
                                hours=self.server.settings.get(
                                    "backups.safety_window_hours", 168
                                )
                            )
                        ).isoformat(),
                    )
                except Exception:
                    cleanup_warning = "Data restored; safety archive protection metadata needs attention. Its pin remains in place."
                try:
                    await run_in_thread(shutil.rmtree, journal.path)
                except OSError:
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
                    except Exception:
                        restart_error = "Data restored successfully, but the server could not restart."
                return RestoreResult(
                    restored=components,
                    safety_backup_id=safety.backup_id,
                    restarted=restarted,
                    restart_error=restart_error,
                    cleanup_warning=cleanup_warning,
                )
