"""Offline application-level backup and disaster recovery engine with full parity to server backups."""

from __future__ import annotations

import asyncio
import gzip
import hashlib
import json
import logging
import os
import shutil
import tarfile
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from securetar import SecureTarArchive

from ..config.const import get_installed_version
from ..db.backup import (
    backup_database,
    get_current_db_revision,
    restore_database,
)
from ..db.database import Database
from ..error import BSMError, ConfigurationError
from ..utils.general import run_async
from ..web.process import check_bsm_offline
from .archive import (
    ARCHIVE_BUFFER_SIZE,
    COMPRESSION_LEVELS,
    BoundedTarInfo,
    _CancellableReader,
    add_json,
    header,
    safe_name,
)
from .credentials import (
    BackupCredentials,
    private_directory,
    protect,
)
from .models import (
    APP_COMPONENTS,
    APP_PREFIXES,
    AppBackupFile,
    AppBackupManifest,
    AppBackupSummary,
    AppComponent,
    AppDrillResult,
    BackupHeader,
)

logger = logging.getLogger(__name__)

EXCLUDED_DIR_NAMES = frozenset(
    {
        "__pycache__",
        ".git",
        ".pytest_cache",
        ".mypy_cache",
        "runtime",
        "node_modules",
        "servers",
        "backups",
        "downloads",
        "content",
        "data",
        "logs",
    }
)
EXCLUDED_EXTENSIONS = frozenset({".pyc", ".pyo", ".pyd", ".tmp", ".log", ".lock"})


class ApplicationBackupError(BSMError):
    """Raised when an application backup or restore operation fails."""


class AppBackupCatalog:
    """Manages metadata, drill status, and index of application backup archives."""

    def __init__(self, directory: Path):
        self.directory = directory
        self.path = directory / "catalog.json"

    def load(self) -> dict[str, Any]:
        if not self.path.is_file():
            return {"archives": {}}
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
            return (
                cast(dict[str, Any], loaded)
                if isinstance(loaded, dict)
                else {"archives": {}}
            )
        except Exception:
            return {"archives": {}}

    def save(self, data: dict[str, Any]) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        temp = self.directory / f".catalog.{uuid4().hex}.tmp"
        temp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        temp.replace(self.path)

    def record_backup(self, summary: AppBackupSummary) -> None:
        data = self.load()
        archives = data.setdefault("archives", {})
        archives[summary.backup_id] = summary.model_dump(mode="json")
        self.save(data)

    def record_drill(self, backup_id: str, drill: AppDrillResult) -> None:
        data = self.load()
        archives = data.setdefault("archives", {})
        if backup_id in archives:
            archives[backup_id]["drill"] = drill.model_dump(mode="json")
        self.save(data)


def assert_bsm_offline(config_dir: str, data_dir: str, db_url: str) -> None:
    """Ensure BSM is offline; raise ApplicationBackupError if running."""
    res = check_bsm_offline(config_dir, data_dir, db_url)
    if asyncio.iscoroutine(res):
        is_offline, pid = run_async(res)
    else:
        is_offline, pid = res
    if not is_offline:
        raise ApplicationBackupError(
            f"Bedrock Server Manager is currently running (PID {pid}). "
            "Application backup and restore operations require BSM to be stopped first.\n"
            "Please stop BSM using 'bsm web stop' (or stop the system service) and retry."
        )


def _compute_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def _copy_tree_filtered(
    src: Path,
    dst: Path,
    excluded_dirs: frozenset[str] = EXCLUDED_DIR_NAMES,
) -> list[tuple[Path, str]]:
    """Copy directory recursively, excluding transient/runtime/server files. Returns (dest_path, rel_path)."""
    copied: list[tuple[Path, str]] = []
    if not src.exists() or not src.is_dir():
        return copied

    dst.mkdir(parents=True, exist_ok=True)
    for root, dirs, files in os.walk(src):
        dirs[:] = [
            d
            for d in dirs
            if d not in excluded_dirs and not d.startswith((".tmp", "tmp"))
        ]

        rel_root = Path(root).relative_to(src)
        target_dir = dst / rel_root
        target_dir.mkdir(parents=True, exist_ok=True)

        for filename in files:
            if any(
                filename.endswith(ext) for ext in EXCLUDED_EXTENSIONS
            ) or filename.startswith(".tmp"):
                continue
            src_file = Path(root) / filename
            dst_file = target_dir / filename
            shutil.copy2(src_file, dst_file)
            rel_file = str(rel_root / filename).replace("\\", "/")
            copied.append((dst_file, rel_file))

    return copied


def get_default_backups_dir(config_dir: str, data_dir: str) -> Path:
    """Resolve the default directory for application backup archives."""
    from ..config import bcm_config

    custom_backup = bcm_config.get_config_value("paths.backups")
    if custom_backup:
        return Path(custom_backup) / "application"
    return Path(data_dir) / "backups" / "application"


def resolve_backup_password(
    config_dir: str,
    hdr: BackupHeader,
    supplied_key: str | None = None,
) -> str | None:
    """Resolve encryption password from local keyring or supplied recovery key."""
    if not hdr.encrypted:
        return None
    if supplied_key:
        return supplied_key
    if not hdr.key_id:
        raise ApplicationBackupError("Encrypted backup has no key identifier.")

    credentials = BackupCredentials(config_dir)
    try:
        record = credentials.get(hdr.key_id)
        return record.secret.get_secret_value()
    except ConfigurationError as error:
        raise ApplicationBackupError(
            f"This backup is encrypted with key '{hdr.key_id}', which is not available in the local keyring.\n"
            "This backup requires a recovery key."
        ) from error


def create_app_backup(
    config_dir: str,
    data_dir: str,
    db_url: str,
    output_path: Path | None = None,
    components: set[AppComponent] | None = None,
    encrypt: bool = True,
    recovery_key: str | None = None,
    compression: str = "balanced",
) -> tuple[Path, AppBackupManifest]:
    """Create a complete, offline application backup archive with SecureTar encryption and component parity."""
    assert_bsm_offline(config_dir, data_dir, db_url)

    selected_components: set[AppComponent] = (
        set(components) if components else set(APP_COMPONENTS)
    )

    now = datetime.now(timezone.utc)
    capture_started = now
    timestamp_str = now.strftime("%Y%m%d_%H%M%S")

    if output_path is None:
        target_dir = get_default_backups_dir(config_dir, data_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        output_path = target_dir / f"bsm_app_backup_{timestamp_str}.bsmappbackup"
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)

    # Resolve encryption credentials
    credentials = BackupCredentials(config_dir)
    password: str | None = None
    kid: str | None = None

    if recovery_key:
        password = recovery_key
        kid = hashlib.sha256(recovery_key.encode("utf-8")).hexdigest()[:16]
    elif encrypt:
        try:
            active_key = credentials.get()
            password = active_key.secret.get_secret_value()
            kid = active_key.key_id
        except ConfigurationError:
            # Keyring not initialized; proceed unencrypted if no key present
            password = None
            kid = None

    alembic_rev: str | None = None

    with tempfile.TemporaryDirectory(prefix="bsm-app-backup-") as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        content_dir = temp_dir / "contents"
        content_dir.mkdir(parents=True, exist_ok=True)

        # 1. Database
        if "database" in selected_components:
            db_content_dir = content_dir / APP_PREFIXES["database"]
            db_content_dir.mkdir(parents=True, exist_ok=True)
            database_instance = Database(db_url)
            database_instance.initialize()
            try:
                alembic_rev = run_async(
                    get_current_db_revision(database_instance.engine)
                )

                json_dump_path = db_content_dir / "db_data.json"
                run_async(backup_database(database_instance, str(json_dump_path)))

                sync_url = database_instance._get_sync_db_url()
                if sync_url.startswith("sqlite:///"):
                    raw_db_path = Path(sync_url.split("sqlite:///")[1])
                    if raw_db_path.is_file():
                        shutil.copy2(raw_db_path, db_content_dir / "database.sqlite3")
            finally:
                database_instance.close()

        # 2. Config directory
        if "config" in selected_components:
            config_path = Path(config_dir)
            if config_path.exists():
                cfg_dst = content_dir / APP_PREFIXES["config"]
                # Exclude credentials directory if credentials component is handled separately
                excluded_from_cfg = EXCLUDED_DIR_NAMES | {"credentials"}
                _copy_tree_filtered(
                    config_path, cfg_dst, excluded_dirs=excluded_from_cfg
                )

        # 3. Credentials
        if "credentials" in selected_components:
            creds_path = Path(config_dir) / "credentials"
            if creds_path.is_dir():
                creds_dst = content_dir / APP_PREFIXES["credentials"]
                _copy_tree_filtered(creds_path, creds_dst)

        # 4. Plugins
        if "plugins" in selected_components:
            plugin_candidates = [
                Path(config_dir) / "plugins",
                Path("plugins"),
            ]
            plugins_dst = content_dir / APP_PREFIXES["plugins"]
            plugins_dst.mkdir(parents=True, exist_ok=True)
            for p_dir in plugin_candidates:
                if p_dir.exists() and p_dir.is_dir():
                    _copy_tree_filtered(p_dir, plugins_dst / p_dir.name)

        # 5. Plugin Data
        if "data" in selected_components:
            data_plugins_dir = Path(data_dir) / "plugins"
            if data_plugins_dir.exists() and data_plugins_dir.is_dir():
                data_dst = content_dir / APP_PREFIXES["data"] / "plugins"
                _copy_tree_filtered(data_plugins_dir, data_dst)

        # Inventory and hash all files
        file_list: list[AppBackupFile] = []
        directories: list[str] = []
        for root, dirs, files in os.walk(content_dir):
            for d in dirs:
                rel_d = str((Path(root) / d).relative_to(content_dir)).replace(
                    "\\", "/"
                )
                directories.append(rel_d)
            for file in sorted(files):
                abs_path = Path(root) / file
                rel_path = str(abs_path.relative_to(content_dir)).replace("\\", "/")
                size = abs_path.stat().st_size
                sha256 = _compute_sha256(abs_path)

                # Determine component association from path prefix
                comp: AppComponent = "config"
                for c_name, prefix in APP_PREFIXES.items():
                    if rel_path == prefix or rel_path.startswith(f"{prefix}/"):
                        comp = c_name
                        break

                file_list.append(
                    AppBackupFile(
                        path=rel_path,
                        component=comp,
                        size=size,
                        executable=os.access(abs_path, os.X_OK)
                        and not abs_path.suffix == ".json",
                        sha256=sha256,
                    )
                )

        manifest = AppBackupManifest(
            backup_id=uuid4(),
            created_at=now,
            capture_started_at=capture_started,
            capture_finished_at=datetime.now(timezone.utc),
            bsm_version=get_installed_version() or "unknown",
            alembic_version=alembic_rev,
            database_type="sqlite" if db_url.startswith("sqlite") else "external",
            components={
                c: "included" if c in selected_components else "absent"
                for c in APP_COMPONENTS
            },
            files=file_list,
            directories=sorted(directories),
            warnings=[],
        )

        # Package payload.tar.gz
        payload_tar = temp_dir / "payload.tar.gz"
        comp_level = COMPRESSION_LEVELS.get(compression, 6)
        with gzip.GzipFile(
            fileobj=payload_tar.open("wb"), mode="wb", compresslevel=comp_level, mtime=0
        ) as gz:
            with tarfile.open(
                fileobj=gz, mode="w|", bufsize=ARCHIVE_BUFFER_SIZE
            ) as tar:
                add_json(tar, "manifest.json", manifest.model_dump(mode="json"))
                for d in manifest.directories:
                    tar_info = tarfile.TarInfo(safe_name(d))
                    tar_info.type = tarfile.DIRTYPE
                    tar_info.mode = 0o700
                    tar.addfile(tar_info)
                for entry in manifest.files:
                    src_file = content_dir / safe_name(entry.path)
                    t_info = tarfile.TarInfo(safe_name(entry.path))
                    t_info.size = entry.size
                    t_info.mode = 0o700 if entry.executable else 0o600
                    with src_file.open("rb", buffering=0) as f_stream:
                        tar.addfile(t_info, f_stream)

        # Wrap in SecureTarArchive v3 with bsm.json container header
        temp_archive = temp_dir / "archive.bsmappbackup"
        with SecureTarArchive(
            temp_archive,
            "w",
            password=password,
            create_version=3,
            bufsize=ARCHIVE_BUFFER_SIZE,
        ) as archive:
            add_json(
                archive.tar,
                "bsm.json",
                BackupHeader(
                    format="bsmbackup",
                    container_version=1,
                    encrypted=password is not None,
                    key_id=kid,
                ).model_dump(),
            )
            info = tarfile.TarInfo("payload.tar.gz")
            info.size = payload_tar.stat().st_size
            info.mode = 0o600
            with payload_tar.open("rb", buffering=0) as source:
                reader = _CancellableReader(source, buffer_size=ARCHIVE_BUFFER_SIZE)
                if password is not None:
                    archive.import_tar(reader, info)
                else:
                    archive.tar.addfile(info, reader)

        if output_path.exists():
            output_path.unlink()
        shutil.move(str(temp_archive), str(output_path))

    # Record in catalog
    catalog = AppBackupCatalog(output_path.parent)
    catalog.record_backup(
        AppBackupSummary(
            backup_id=str(manifest.backup_id),
            filename=output_path.name,
            created_at=manifest.created_at.isoformat(),
            size=output_path.stat().st_size,
            encrypted=password is not None,
            key_id=kid,
            components=manifest.components,
            manifest=manifest,
        )
    )

    return output_path, manifest


def unpack_app_archive(
    archive_path: Path,
    destination: Path,
    password: str | None = None,
    materialize: bool = True,
) -> AppBackupManifest:
    """Authenticate and extract a SecureTar v3 application backup archive."""
    if not archive_path.is_file():
        raise ApplicationBackupError(f"Backup archive not found: {archive_path}")

    hdr = header(archive_path)
    if hdr.encrypted and not password:
        raise ApplicationBackupError(
            f"This backup is encrypted (key_id: {hdr.key_id or 'unknown'}) and requires a recovery key."
        )

    try:
        private_directory(destination)
        with SecureTarArchive(
            archive_path, "r", password=password if hdr.encrypted else None
        ) as archive:
            archive.tar.tarinfo = BoundedTarInfo
            members = []
            for _ in range(3):
                m = archive.tar.next()
                if m is None:
                    break
                members.append(m)

            if (
                len(members) != 2
                or members[1].name != "payload.tar.gz"
                or not members[1].isfile()
            ):
                raise ApplicationBackupError("Invalid outer container inventory.")

            source = (
                archive.extract_tar(members[1])
                if hdr.encrypted
                else archive.tar.extractfile(members[1])
            )
            assert source is not None

            packed = destination / f".payload.{uuid4().hex}"
            try:
                with source as decrypted, open(packed, "wb") as output:
                    shutil.copyfileobj(decrypted, output)

                with tarfile.open(packed, mode="r:gz") as payload_tar:
                    manifest_member = payload_tar.getmember("manifest.json")
                    f_stream = payload_tar.extractfile(manifest_member)
                    assert f_stream is not None
                    manifest = AppBackupManifest.model_validate_json(f_stream.read())

                    if materialize:
                        for member in payload_tar.getmembers():
                            if member.name == "manifest.json":
                                continue
                            target_file = destination / member.name
                            if member.isdir():
                                target_file.mkdir(parents=True, exist_ok=True)
                            elif member.isfile():
                                target_file.parent.mkdir(parents=True, exist_ok=True)
                                src = payload_tar.extractfile(member)
                                if src is not None:
                                    with src, open(target_file, "wb") as dst:
                                        shutil.copyfileobj(src, dst)
                return manifest
            finally:
                if packed.is_file():
                    packed.unlink(missing_ok=True)
    except ApplicationBackupError:
        raise
    except Exception as error:
        raise ApplicationBackupError(
            f"Failed to unpack application backup: {error}"
        ) from error


def inspect_app_backup(
    archive_path: Path,
    config_dir: str | None = None,
    recovery_key: str | None = None,
) -> tuple[BackupHeader, AppBackupManifest]:
    """Inspect backup header and manifest without full extraction."""
    hdr = header(archive_path)
    password: str | None = None
    if hdr.encrypted:
        if recovery_key:
            password = recovery_key
        elif config_dir:
            password = resolve_backup_password(config_dir, hdr)

    with tempfile.TemporaryDirectory(prefix="bsm-app-inspect-") as temp_dir:
        manifest = unpack_app_archive(
            archive_path,
            Path(temp_dir),
            password=password,
            materialize=False,
        )
    return hdr, manifest


def drill_app_backup(
    archive_path: Path,
    config_dir: str,
    data_dir: str,
    db_url: str,
    recovery_key: str | None = None,
) -> AppDrillResult:
    """Execute an isolated recovery drill verifying archive integrity and component syntax."""
    started_perf = time.perf_counter()
    started_iso = datetime.now(timezone.utc).isoformat()
    hdr = header(archive_path)
    password = resolve_backup_password(config_dir, hdr, recovery_key)

    with tempfile.TemporaryDirectory(prefix="bsm-app-drill-") as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        try:
            manifest = unpack_app_archive(
                archive_path,
                temp_dir,
                password=password,
                materialize=True,
            )

            checked_files = 0
            # 1. Verify every file hash
            for f_entry in manifest.files:
                target = temp_dir / f_entry.path
                if not target.is_file():
                    raise ApplicationBackupError(
                        f"Drill failed: missing file '{f_entry.path}'"
                    )
                actual_hash = _compute_sha256(target)
                if actual_hash != f_entry.sha256:
                    raise ApplicationBackupError(
                        f"Drill failed: hash mismatch on '{f_entry.path}'"
                    )
                checked_files += 1

            # 2. Verify database component syntax
            if manifest.components.get("database") == "included":
                json_db = temp_dir / APP_PREFIXES["database"] / "db_data.json"
                if json_db.is_file():
                    db_dict = json.loads(json_db.read_text(encoding="utf-8"))
                    if not isinstance(db_dict, dict):
                        raise ApplicationBackupError(
                            "Drill failed: db_data.json is not a valid JSON object."
                        )

            # 3. Verify config component syntax
            if manifest.components.get("config") == "included":
                cfg_dir = temp_dir / APP_PREFIXES["config"]
                if cfg_dir.is_dir():
                    for json_f in cfg_dir.glob("**/*.json"):
                        json.loads(json_f.read_text(encoding="utf-8"))

            duration_ms = (time.perf_counter() - started_perf) * 1000
            result = AppDrillResult(
                backup_id=str(manifest.backup_id),
                checked_at=started_iso,
                status="passed",
                checked_files=checked_files,
                checked_components=[
                    c for c, s in manifest.components.items() if s == "included"
                ],
                duration_ms=round(duration_ms, 2),
            )
        except Exception as e:
            duration_ms = (time.perf_counter() - started_perf) * 1000
            result = AppDrillResult(
                backup_id=archive_path.stem,
                checked_at=started_iso,
                status="failed",
                checked_files=0,
                checked_components=[],
                duration_ms=round(duration_ms, 2),
                error=str(e),
            )

    # Save drill in catalog
    catalog = AppBackupCatalog(archive_path.parent)
    catalog.record_drill(result.backup_id, result)
    return result


def restore_app_backup(
    archive_path: Path,
    config_dir: str,
    data_dir: str,
    db_url: str,
    components: set[AppComponent] | None = None,
    recovery_key: str | None = None,
) -> AppBackupManifest:
    """Selectively restore an application backup while BSM is offline."""
    assert_bsm_offline(config_dir, data_dir, db_url)

    hdr = header(archive_path)
    password = resolve_backup_password(config_dir, hdr, recovery_key)

    with tempfile.TemporaryDirectory(prefix="bsm-app-restore-") as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        manifest = unpack_app_archive(
            archive_path,
            temp_dir,
            password=password,
            materialize=True,
        )

        # Determine target components to restore
        restore_components = (
            components
            if components
            else {c for c, s in manifest.components.items() if s == "included"}
        )

        # Check integrity of target files
        for f_entry in manifest.files:
            if f_entry.component not in restore_components:
                continue
            target_file = temp_dir / f_entry.path
            if not target_file.is_file():
                raise ApplicationBackupError(
                    f"Integrity check failed: missing file '{f_entry.path}'."
                )
            if _compute_sha256(target_file) != f_entry.sha256:
                raise ApplicationBackupError(
                    f"Integrity check failed: checksum mismatch for '{f_entry.path}'."
                )

        # 1. Restore Config
        if "config" in restore_components:
            src_cfg = temp_dir / APP_PREFIXES["config"]
            if src_cfg.is_dir():
                dst_cfg = Path(config_dir)
                dst_cfg.mkdir(parents=True, exist_ok=True)
                for item in src_cfg.iterdir():
                    if item.name in EXCLUDED_DIR_NAMES:
                        continue
                    dst_item = dst_cfg / item.name
                    if item.is_dir():
                        shutil.copytree(item, dst_item, dirs_exist_ok=True)
                    else:
                        shutil.copy2(item, dst_item)

        # 2. Restore Credentials
        if "credentials" in restore_components:
            src_creds = temp_dir / APP_PREFIXES["credentials"]
            if src_creds.is_dir():
                dst_creds = Path(config_dir) / "credentials"
                private_directory(dst_creds)
                for item in src_creds.iterdir():
                    dst_item = dst_creds / item.name
                    if item.is_file():
                        shutil.copy2(item, dst_item)
                        protect(dst_item)

        # 3. Restore Plugins
        if "plugins" in restore_components:
            src_plugins = temp_dir / APP_PREFIXES["plugins"]
            if src_plugins.is_dir():
                primary_plugin_dir = Path(config_dir) / "plugins"
                primary_plugin_dir.mkdir(parents=True, exist_ok=True)
                for item in src_plugins.iterdir():
                    dst_item = primary_plugin_dir / item.name
                    if item.is_dir():
                        shutil.copytree(item, dst_item, dirs_exist_ok=True)
                    else:
                        shutil.copy2(item, dst_item)

        # 4. Restore Plugin Data
        if "data" in restore_components:
            src_data = temp_dir / APP_PREFIXES["data"]
            if src_data.is_dir():
                dst_data = Path(data_dir)
                dst_data.mkdir(parents=True, exist_ok=True)
                shutil.copytree(src_data, dst_data, dirs_exist_ok=True)

        # 5. Restore Database
        if "database" in restore_components:
            src_db_dir = temp_dir / APP_PREFIXES["database"]
            if src_db_dir.is_dir():
                raw_sqlite = src_db_dir / "database.sqlite3"
                json_dump = src_db_dir / "db_data.json"

                database_instance = Database(db_url)
                database_instance.initialize()
                try:
                    sync_url = database_instance._get_sync_db_url()
                    if raw_sqlite.is_file() and sync_url.startswith("sqlite:///"):
                        target_db_path = Path(sync_url.split("sqlite:///")[1])
                        target_db_path.parent.mkdir(parents=True, exist_ok=True)
                        database_instance.close()
                        shutil.copy2(raw_sqlite, target_db_path)
                    elif json_dump.is_file():
                        content = json_dump.read_text(encoding="utf-8")
                        backup_data = json.loads(content)
                        run_async(restore_database(database_instance, backup_data))
                finally:
                    database_instance.close()

    return manifest


def list_app_backups(
    search_dirs: list[Path],
    config_dir: str | None = None,
) -> list[tuple[Path, BackupHeader, AppBackupManifest | None]]:
    """Scan directories for application backups, reading headers and catalog metadata."""
    results: list[tuple[Path, BackupHeader, AppBackupManifest | None]] = []
    seen: set[str] = set()

    for s_dir in search_dirs:
        if not s_dir.exists() or not s_dir.is_dir():
            continue

        catalog = AppBackupCatalog(s_dir)
        cat_data = catalog.load().get("archives", {})

        for candidate in sorted(s_dir.iterdir()):
            if not candidate.is_file():
                continue
            if not (
                candidate.name.endswith(".bsmappbackup")
                or candidate.name.endswith(".bsmbackup")
            ):
                continue

            resolved = str(candidate.resolve())
            if resolved in seen:
                continue
            seen.add(resolved)

            try:
                hdr = header(candidate)
                manifest: AppBackupManifest | None = None
                # Check catalog cache first
                for c_rec in cat_data.values():
                    if c_rec.get("filename") == candidate.name and c_rec.get(
                        "manifest"
                    ):
                        try:
                            manifest = AppBackupManifest.model_validate_json(
                                json.dumps(c_rec["manifest"])
                            )
                        except Exception:
                            manifest = None
                        break

                if manifest is None and (not hdr.encrypted or config_dir):
                    try:
                        _, manifest = inspect_app_backup(
                            candidate, config_dir=config_dir
                        )
                    except Exception:
                        manifest = None

                results.append((candidate, hdr, manifest))
            except Exception:
                continue

    results.sort(
        key=lambda item: (
            item[2].created_at if item[2] else datetime.min.replace(tzinfo=timezone.utc)
        ),
        reverse=True,
    )
    return results
