"""Bounded SecureTar v3 containers, shared by the server and offline recovery."""

import gzip
import hashlib
import io
import json
import logging
import os
import re
import tarfile
import tempfile
import threading
import time
from contextlib import ExitStack, nullcontext
from pathlib import Path, PurePosixPath
from typing import Any

from securetar import SecureTarArchive, SecureTarHeader

from ..error import BackupRestoreError
from ..utils.threads import check_cancellation
from .credentials import private_directory
from .models import PREFIXES, BackupHeader, BackupManifest
from .spool import CaptureSpool
from .work import FileWork

MAX_FILES = 1_000_000
MAX_BYTES = 1024**4
MAX_METADATA = 32 * 1024 * 1024
RESERVED = re.compile(r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)", re.I)


class _CancellableReader(io.BufferedReader):
    cancellation_event: threading.Event | None = None

    def read(self, size: int | None = -1) -> bytes:
        check_cancellation(self.cancellation_event)
        data = super().read(size)
        check_cancellation(self.cancellation_event)
        return data


class _MeasuredReader(_CancellableReader):
    """Measure source reads without counting tar/gzip work between reads."""

    read_seconds: float = 0.0
    bytes_read: int = 0

    def read(self, size: int | None = -1) -> bytes:
        started = time.perf_counter()
        try:
            data = super().read(size)
        finally:
            self.read_seconds += time.perf_counter() - started
        self.bytes_read += len(data)
        return data


class BoundedTarInfo(tarfile.TarInfo):
    """Bound extended headers before tarfile allocates their metadata buffers."""

    def _proc_pax(self, archive):
        if self.size > MAX_METADATA:
            raise ValueError("Archive metadata exceeds limit")
        return super()._proc_pax(archive)

    def _proc_gnulong(self, archive):
        if self.size > MAX_METADATA:
            raise ValueError("Archive metadata exceeds limit")
        return super()._proc_gnulong(archive)


def safe_name(value: str) -> str:
    """Require portable relative paths on every supported platform."""
    path = PurePosixPath(value)
    if (
        not value
        or len(value) > 1024
        or value != path.as_posix()
        or path.is_absolute()
        or "\\" in value
        or any(
            part in (".", "..")
            or part.endswith((" ", "."))
            or any(ord(c) < 32 or c in ':<>"|?*' for c in part)
            or RESERVED.match(part)
            for part in path.parts
        )
    ):
        raise BackupRestoreError("Backup contains an unsafe path.")
    return value


def digest(path: Path, cancellation_event: threading.Event | None = None) -> str:
    result = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            check_cancellation(cancellation_event)
            result.update(chunk)
    return result.hexdigest()


def add_json(archive: tarfile.TarFile, name: str, data: Any) -> None:
    encoded = json.dumps(data, allow_nan=False).encode()
    info = tarfile.TarInfo(name)
    info.size = len(encoded)
    info.mode = 0o600
    archive.addfile(info, io.BytesIO(encoded))


def header(path: Path) -> BackupHeader:
    """Read only the bounded public header, without trying legacy formats."""
    try:
        with tarfile.open(path, "r:", tarinfo=BoundedTarInfo) as archive:
            member = archive.next()
            if (
                member is None
                or member.name != "bsm.json"
                or not member.isfile()
                or member.size > 4096
            ):
                raise ValueError
            stream = archive.extractfile(member)
            assert stream is not None
            result = BackupHeader.model_validate_json(stream.read())
            if result.encrypted != bool(result.key_id):
                raise ValueError
            return result
    except (OSError, ValueError, tarfile.TarError) as error:
        raise BackupRestoreError("Invalid or unsupported BSM backup header.") from error


ARCHIVE_BUFFER_SIZE = 1024 * 1024
COMPRESSION_LEVELS = {"fast": 1, "balanced": 6, "small": 9}


def build_payload(
    staging: Path,
    target: Path,
    manifest: BackupManifest,
    compression: str = "balanced",
    cancellation_event: threading.Event | None = None,
    *,
    spool: CaptureSpool | None = None,
) -> None:
    """Build a portable gzip payload using a supported compression level."""
    level = COMPRESSION_LEVELS[compression]
    logger = logging.getLogger(__name__)
    logger.debug(
        "Backup payload started: compression=%s gzip_level=%d files=%d",
        compression,
        level,
        len(manifest.files),
    )
    started = time.perf_counter()
    open_seconds = read_seconds = close_seconds = 0.0
    bytes_read = 0
    spooled_files = 0
    with ExitStack() as resources:
        spool_reader = None
        if spool is not None:
            opened = time.perf_counter()
            spool_reader = resources.enter_context(
                _MeasuredReader(spool.path.open("rb"))
            )
            spool_reader.cancellation_event = cancellation_event
            open_seconds += time.perf_counter() - opened
        output = resources.enter_context(
            target.open("wb", buffering=ARCHIVE_BUFFER_SIZE)
        )
        with gzip.GzipFile(
            fileobj=output, mode="wb", compresslevel=level, mtime=0
        ) as compressed:
            with tarfile.open(
                fileobj=compressed, mode="w|", bufsize=ARCHIVE_BUFFER_SIZE
            ) as payload:
                add_json(payload, "manifest.json", manifest.model_dump(mode="json"))
                for name in manifest.directories:
                    check_cancellation(cancellation_event)
                    info = tarfile.TarInfo(safe_name(name))
                    info.type = tarfile.DIRTYPE
                    info.mode = 0o700
                    payload.addfile(info)
                for item in manifest.files:
                    check_cancellation(cancellation_event)
                    source = staging / safe_name(item.path)
                    info = tarfile.TarInfo(item.path)
                    info.mode = 0o700 if item.executable else 0o600
                    info.size = item.size
                    opened = time.perf_counter()
                    offset = spool.offset(source) if spool is not None else None
                    if offset is not None and spool_reader is not None:
                        spool_reader.seek(offset)
                        open_seconds += time.perf_counter() - opened
                        before = spool_reader.read_seconds
                        before_bytes = spool_reader.bytes_read
                        payload.addfile(info, spool_reader)
                        read_seconds += spool_reader.read_seconds - before
                        bytes_read += spool_reader.bytes_read - before_bytes
                        spooled_files += 1
                    else:
                        reader = _MeasuredReader(source.open("rb"))
                        open_seconds += time.perf_counter() - opened
                        try:
                            reader.cancellation_event = cancellation_event
                            payload.addfile(info, reader)
                            read_seconds += reader.read_seconds
                            bytes_read += reader.bytes_read
                        finally:
                            closing = time.perf_counter()
                            reader.close()
                            close_seconds += time.perf_counter() - closing
    total = time.perf_counter() - started
    source_seconds = open_seconds + read_seconds + close_seconds
    logger.debug(
        "Backup payload completed: compression=%s gzip_level=%d files=%d "
        "spooled_files=%d bytes_read=%d source_open_ms=%.3f source_read_ms=%.3f "
        "source_close_ms=%.3f archive_other_ms=%.3f total_ms=%.3f "
        "(archive_other includes tar, gzip, output I/O, metadata, and finalization)",
        compression,
        level,
        len(manifest.files),
        spooled_files,
        bytes_read,
        open_seconds * 1000,
        read_seconds * 1000,
        close_seconds * 1000,
        max(0.0, total - source_seconds) * 1000,
        total * 1000,
    )


def write_archive(
    staging: Path,
    target: Path,
    manifest: BackupManifest,
    password: str | None,
    key_id: str | None,
    cancellation_event: threading.Event | None = None,
    *,
    compression: str = "balanced",
    prepared_payload: Path | None = None,
) -> None:
    """Publish a gzip payload into the existing SecureTar v3 container."""

    def package(payload: Path) -> None:
        check_cancellation(cancellation_event)
        with SecureTarArchive(
            target,
            "w",
            password=password,
            create_version=3,
            bufsize=ARCHIVE_BUFFER_SIZE,
        ) as archive:
            add_json(
                archive.tar,
                "bsm.json",
                BackupHeader(
                    encrypted=password is not None, key_id=key_id
                ).model_dump(),
            )
            info = tarfile.TarInfo("payload.tar.gz")
            info.size = payload.stat().st_size
            info.mode = 0o600
            with (
                payload.open("rb", buffering=0) as source,
                _CancellableReader(source, buffer_size=ARCHIVE_BUFFER_SIZE) as reader,
            ):
                reader.cancellation_event = cancellation_event
                if password is not None:
                    archive.import_tar(reader, info)
                else:
                    archive.tar.addfile(info, reader)
        # Flush the completed archive once, before the caller atomically publishes it.
        with target.open("r+b") as completed:
            os.fsync(completed.fileno())

    if prepared_payload is not None:
        package(prepared_payload)
    else:
        with tempfile.TemporaryDirectory(
            prefix=".bsm-payload-", dir=target.parent
        ) as directory:
            private_directory(Path(directory))
            payload = Path(directory) / "payload.tar.gz"
            build_payload(staging, payload, manifest, compression, cancellation_event)
            package(payload)


def publish_archive(source: Path, destination: Path) -> None:
    """Publish an already-flushed archive and persist the directory entry."""
    os.replace(source, destination)
    if os.name != "nt":
        descriptor = os.open(destination.parent, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def manifest_requirements(manifest: BackupManifest) -> dict[str, int]:
    """Use the same entry/byte accounting as the portable reader."""
    encoded = json.dumps(manifest.model_dump(mode="json"), allow_nan=False).encode()
    return {
        "entries": 1 + len(manifest.files) + len(manifest.directories),
        "expanded_bytes": len(encoded) + sum(item.size for item in manifest.files),
        "metadata_bytes": len(encoded),
    }


def check_manifest_limits(manifest, max_bytes=MAX_BYTES, max_files=MAX_FILES):
    requirements = manifest_requirements(manifest)
    if (
        requirements["entries"] > max_files
        or requirements["expanded_bytes"] > max_bytes
        or requirements["metadata_bytes"] > MAX_METADATA
    ):
        raise BackupRestoreError("Backup contents exceed configured recovery limits.")
    validate_manifest(manifest)
    return requirements


def unpack(
    path: Path,
    destination: Path,
    password: str | None = None,
    *,
    max_bytes: int = MAX_BYTES,
    max_files: int = MAX_FILES,
    cancellation_event: threading.Event | None = None,
    materialize: bool = True,
    stage_callback=None,
    read_stats=None,
    durable: bool = False,
) -> BackupManifest:
    """Authenticate the complete stream and validate inventory before using contents."""
    from .space import ensure_free_space

    if durable and not materialize:
        raise ValueError("Durable extraction requires materialized files")
    work = (
        FileWork("Extracting durable restore files", stage_callback)
        if durable
        else None
    )
    public = header(path)
    if public.encrypted and not password:
        raise BackupRestoreError("This backup requires its recovery key.")
    try:
        private_directory(destination)
        with SecureTarArchive(
            path, "r", password=password if public.encrypted else None
        ) as archive:
            archive.tar.tarinfo = BoundedTarInfo
            members = []
            for _ in range(3):
                member = archive.tar.next()
                if member is None:
                    break
                members.append(member)
            if (
                len(members) != 2
                or members[1].name != "payload.tar.gz"
                or not members[1].isfile()
            ):
                raise ValueError("Invalid outer inventory")
            if public.encrypted:
                encrypted_stream = archive.tar.extractfile(members[1])
                assert encrypted_stream is not None
                with encrypted_stream:
                    encryption_header = SecureTarHeader.from_bytes(encrypted_stream)
                if encryption_header.version != 3:
                    raise ValueError("Unsupported encryption format")
            # Reserve space before materializing the authenticated compressed stream.
            ensure_free_space(destination, members[1].size)
            if stage_callback is not None:
                stage_callback("Authenticating backup payload")
            authenticated_at = time.monotonic()
            packed = destination / ".payload"
            source = (
                archive.extract_tar(members[1])
                if public.encrypted
                else archive.tar.extractfile(members[1])
            )
            assert source is not None
            with source as decrypted, packed.open("wb") as output:
                total = 0
                while chunk := decrypted.read(1024 * 1024):
                    check_cancellation(cancellation_event)
                    total += len(chunk)
                    if total > max_bytes:
                        raise ValueError("Archive exceeds size limit")
                    output.write(chunk)
        logging.getLogger(__name__).debug(
            "Backup payload authenticated: duration_ms=%.3f",
            (time.monotonic() - authenticated_at) * 1000,
        )
        if stage_callback is not None:
            stage_callback(
                "Extracting and hashing backup contents"
                if materialize
                else "Validating backup inventory and checksums"
            )
        extraction_started = time.monotonic()
        last_progress = extraction_started
        completed_files = 0
        seen: dict[str, bool] = {}
        ancestors: set[str] = set()
        total = 0
        manifest = None
        with tarfile.open(packed, "r|gz", tarinfo=BoundedTarInfo) as payload:
            for member in payload:
                check_cancellation(cancellation_event)
                name = safe_name(member.name)
                folded = name.casefold()
                if (
                    folded in seen
                    or not (member.isfile() or member.isdir())
                    or len(seen) >= max_files
                ):
                    raise ValueError("Invalid or duplicate entry")
                parents = {
                    str(parent).casefold() for parent in PurePosixPath(name).parents
                }
                if any(seen.get(parent) is False for parent in parents):
                    raise ValueError("Conflicting entry")
                if member.isfile() and folded in ancestors:
                    raise ValueError("Conflicting entry")
                ancestors.update(parents)
                seen[folded] = member.isdir()
                total += member.size
                if total > max_bytes or member.size < 0:
                    raise ValueError("Archive exceeds size limit")
                if manifest is None:
                    if (
                        name != "manifest.json"
                        or not member.isfile()
                        or member.size > MAX_METADATA
                    ):
                        raise ValueError("Manifest must be first")
                    stream = payload.extractfile(member)
                    assert stream is not None
                    manifest = BackupManifest.model_validate_json(stream.read())
                    check_manifest_limits(manifest, max_bytes, max_files)
                    if materialize:
                        ensure_free_space(
                            destination,
                            sum(item.size for item in manifest.files)
                            + len(manifest.files) * 4096
                            + len(manifest.directories) * 4096,
                        )
                    file_inventory = {item.path: item for item in manifest.files}
                    directory_inventory = set(manifest.directories)
                    continue
                expected_file = file_inventory.get(name)
                if member.isfile() and (
                    expected_file is None or expected_file.size != member.size
                ):
                    raise ValueError("Unexpected file")
                if member.isdir() and name not in directory_inventory:
                    raise ValueError("Unexpected directory")
                target = destination / name
                if member.isdir():
                    if materialize:
                        target.mkdir(parents=True, exist_ok=True, mode=0o700)
                else:
                    assert expected_file is not None
                    if materialize:
                        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                    stream = payload.extractfile(member)
                    assert stream is not None
                    checksum = hashlib.sha256()
                    with work.phase("open") if work else nullcontext():
                        extracted_output = target.open("wb") if materialize else None
                    try:
                        with stream:
                            while True:
                                check_cancellation(cancellation_event)
                                with work.phase("read") if work else nullcontext():
                                    chunk = stream.read(1024 * 1024)
                                if not chunk:
                                    break
                                check_cancellation(cancellation_event)
                                with work.phase("hash") if work else nullcontext():
                                    checksum.update(chunk)
                                if extracted_output is not None:
                                    with work.phase("write") if work else nullcontext():
                                        extracted_output.write(chunk)
                                moment = time.monotonic()
                                if (
                                    stage_callback is not None
                                    and moment - last_progress >= 1
                                ):
                                    stage_callback(
                                        f"Validating backup contents ({completed_files}/{len(manifest.files)} files)"
                                    )
                                    last_progress = moment
                        if checksum.hexdigest() != expected_file.sha256:
                            raise ValueError("Checksum mismatch")
                        if extracted_output is not None and durable:
                            assert work is not None
                            with work.phase("permissions"):
                                if os.name != "nt":
                                    os.fchmod(
                                        extracted_output.fileno(),
                                        0o700 if expected_file.executable else 0o600,
                                    )
                            check_cancellation(cancellation_event)
                            with work.phase("flush"):
                                extracted_output.flush()
                            with work.phase("fsync"):
                                os.fsync(extracted_output.fileno())
                        elif (
                            materialize and expected_file.executable and os.name != "nt"
                        ):
                            target.chmod(0o700)
                    finally:
                        if extracted_output is not None:
                            with work.phase("close") if work else nullcontext():
                                extracted_output.close()
                    completed_files += 1
                    if work is not None:
                        work.files += 1
                        work.bytes += expected_file.size
        if read_stats is not None:
            read_stats["payload_bytes"] = packed.stat().st_size
        packed.unlink()
        if manifest is None:
            raise ValueError("Missing manifest")
        expected = {item.path.casefold(): False for item in manifest.files}
        expected.update({name.casefold(): True for name in manifest.directories})
        if {
            key: value for key, value in seen.items() if key != "manifest.json"
        } != expected:
            raise ValueError("Inventory mismatch")
        logging.getLogger(__name__).debug(
            "Backup inventory validated: files=%d materialized=%s duration_ms=%.3f",
            len(manifest.files),
            materialize,
            (time.monotonic() - extraction_started) * 1000,
        )
        if durable:
            from .recovery import sync_tree

            sync_tree(
                destination,
                cancellation_event,
                stage_callback=stage_callback,
                include_files=False,
            )
        if work is not None:
            work.finish("completed")
        return manifest
    except (BackupRestoreError, InterruptedError):
        if work is not None:
            work.finish("failed")
        raise
    except Exception as error:
        if work is not None:
            work.finish("failed")
        # Never include potentially secret archive values in the public error.
        raise BackupRestoreError(
            "Backup validation failed: wrong key, damaged data, or invalid inventory."
        ) from error


def validate_manifest(manifest: BackupManifest) -> None:
    from .models import BASE_COMPONENTS, COMPONENTS, DIRECTORY_COMPONENTS

    if not set(BASE_COMPONENTS).issubset(manifest.components) or not set(
        manifest.components
    ).issubset(COMPONENTS):
        raise ValueError("Incomplete component inventory")
    for name in [item.path for item in manifest.files] + manifest.directories:
        parts = name.split("/")
        if (
            parts[0] == "server-directory"
            and len(parts) > 1
            and parts[1].casefold().startswith(".bsm-")
        ):
            raise ValueError("Reserved BSM internal storage")
    names = [safe_name(item.path).casefold() for item in manifest.files]
    names += [safe_name(name).casefold() for name in manifest.directories]
    if len(set(names)) != len(names) or "manifest.json" in names:
        raise ValueError("Duplicate manifest path")
    for item in manifest.files:
        prefix = PREFIXES[item.component]
        if manifest.components[item.component] != "included" or not (
            item.path == prefix
            or item.path.startswith(prefix + "/")
            and item.component in DIRECTORY_COMPONENTS
        ):
            raise ValueError("Invalid component path")
    for name in manifest.directories:
        if not any(
            manifest.components[c] == "included"
            and (name == PREFIXES[c] or name.startswith(PREFIXES[c] + "/"))
            for c in DIRECTORY_COMPONENTS
            if c in manifest.components
        ):
            raise ValueError("Invalid directory")
    for component, state in manifest.components.items():
        if state == "included" and PREFIXES[component].casefold() not in names:
            raise ValueError("Missing component root")
