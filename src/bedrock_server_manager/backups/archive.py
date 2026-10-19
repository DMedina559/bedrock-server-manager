"""Bounded SecureTar v3 containers, shared by the server and offline recovery."""

import hashlib
import io
import json
import os
import re
import shutil
import tarfile
from pathlib import Path, PurePosixPath
from typing import Any

from securetar import SecureTarArchive, SecureTarHeader

from ..error import BackupRestoreError
from .models import PREFIXES, BackupHeader, BackupManifest

MAX_FILES = 1_000_000
MAX_BYTES = 1024**4
MAX_METADATA = 32 * 1024 * 1024
RESERVED = re.compile(r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)", re.I)


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


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
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


def write_archive(
    staging: Path,
    target: Path,
    manifest: BackupManifest,
    password: str | None,
    key_id: str | None,
) -> None:
    """Write to a private temporary target; the caller publishes after verification."""
    with SecureTarArchive(target, "w", password=password, create_version=3) as archive:
        add_json(
            archive.tar,
            "bsm.json",
            BackupHeader(encrypted=password is not None, key_id=key_id).model_dump(),
        )
        with archive.create_tar("payload.tar.gz") as payload:
            add_json(payload, "manifest.json", manifest.model_dump(mode="json"))
            for name in manifest.directories:
                info = tarfile.TarInfo(safe_name(name))
                info.type = tarfile.DIRTYPE
                info.mode = 0o700
                payload.addfile(info)
            for item in manifest.files:
                source = staging / safe_name(item.path)
                info = tarfile.TarInfo(item.path)
                info.mode = 0o600
                info.size = item.size
                with source.open("rb") as stream:
                    payload.addfile(info, stream)
    with target.open("rb") as stream:
        os.fsync(stream.fileno())


def unpack(
    path: Path,
    destination: Path,
    password: str | None = None,
    *,
    max_bytes: int = MAX_BYTES,
    max_files: int = MAX_FILES,
) -> BackupManifest:
    """Authenticate the complete stream and validate inventory before using contents."""
    public = header(path)
    if public.encrypted and not password:
        raise BackupRestoreError("This backup requires its recovery key.")
    try:
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
            # Consume and authenticate to the final tag before parsing or applying data.
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
                    total += len(chunk)
                    if total > max_bytes:
                        raise ValueError("Archive exceeds size limit")
                    output.write(chunk)
        seen: dict[str, bool] = {}
        total = 0
        manifest = None
        with tarfile.open(packed, "r|gz", tarinfo=BoundedTarInfo) as payload:
            for member in payload:
                name = safe_name(member.name)
                folded = name.casefold()
                if (
                    folded in seen
                    or not (member.isfile() or member.isdir())
                    or len(seen) >= max_files
                ):
                    raise ValueError("Invalid or duplicate entry")
                for parent in PurePosixPath(name).parents:
                    if seen.get(str(parent).casefold()) is False:
                        raise ValueError("Conflicting entry")
                if member.isfile() and any(
                    key.startswith(folded + "/") for key in seen
                ):
                    raise ValueError("Conflicting entry")
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
                    validate_manifest(manifest)
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
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    stream = payload.extractfile(member)
                    assert stream is not None
                    with stream, target.open("wb") as output:
                        shutil.copyfileobj(stream, output, 1024 * 1024)
        packed.unlink()
        if manifest is None:
            raise ValueError("Missing manifest")
        expected = {item.path.casefold(): False for item in manifest.files}
        expected.update({name.casefold(): True for name in manifest.directories})
        if {
            key: value for key, value in seen.items() if key != "manifest.json"
        } != expected:
            raise ValueError("Inventory mismatch")
        for item in manifest.files:
            extracted = destination / item.path
            if (
                extracted.stat().st_size != item.size
                or digest(extracted) != item.sha256
            ):
                raise ValueError("Checksum mismatch")
        return manifest
    except BackupRestoreError:
        raise
    except Exception as error:
        # Never include potentially secret archive values in the public error.
        raise BackupRestoreError(
            "Backup validation failed: wrong key, damaged data, or invalid inventory."
        ) from error


def validate_manifest(manifest: BackupManifest) -> None:
    from .models import COMPONENTS

    if set(manifest.components) != set(COMPONENTS):
        raise ValueError("Incomplete component inventory")
    names = [safe_name(item.path).casefold() for item in manifest.files]
    names += [safe_name(name).casefold() for name in manifest.directories]
    if len(set(names)) != len(names) or "manifest.json" in names:
        raise ValueError("Duplicate manifest path")
    for item in manifest.files:
        prefix = PREFIXES[item.component]
        if manifest.components[item.component] != "included" or not (
            item.path == prefix
            or item.path.startswith(prefix + "/")
            and item.component in ("world", "script_config")
        ):
            raise ValueError("Invalid component path")
    for name in manifest.directories:
        if not any(
            manifest.components[c] == "included"
            and (name == PREFIXES[c] or name.startswith(PREFIXES[c] + "/"))
            for c in ("world", "script_config")
        ):
            raise ValueError("Invalid directory")
    for component, state in manifest.components.items():
        if state == "included" and PREFIXES[component].casefold() not in names:
            raise ValueError("Missing component root")
