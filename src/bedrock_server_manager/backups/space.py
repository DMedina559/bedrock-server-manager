"""Conservative restore capacity estimates grouped by physical filesystem."""

import os
import shutil
import stat
from pathlib import Path

from ..error import BackupRestoreError
from ..utils.threads import check_cancellation
from .archive import safe_name
from .models import PACK_COMPONENTS, RestoreVolume

HEADROOM = 16 * 1024 * 1024


def ensure_free_space(path: Path, required: int) -> None:
    """Fail before writing temporary data, retaining conservative headroom."""
    if shutil.disk_usage(existing_parent(path)).free < required + HEADROOM:
        raise BackupRestoreError("Insufficient space for backup staging or recovery.")


def scan_source_tree(
    root: Path,
    cancellation_event=None,
    *,
    is_link_fn=None,
    max_files: int | None = None,
    max_bytes: int | None = None,
) -> tuple[int, int]:
    """Validate source tree safety and compute total size/count in a single pass."""
    check_cancellation(cancellation_event)
    if is_link_fn is not None and is_link_fn(root):
        raise BackupRestoreError("Backup sources must not contain symbolic links.")
    safe_name(root.name)

    if root.is_file():
        st = root.stat()
        return st.st_size, 1
    if not root.is_dir():
        raise BackupRestoreError("Backup sources must be regular files.")

    size = 0
    count = 1

    def _walk(dir_path: str) -> None:
        nonlocal size, count
        with os.scandir(dir_path) as it:
            for entry in it:
                check_cancellation(cancellation_event)
                is_link = entry.is_symlink()
                st = entry.stat(follow_symlinks=False)
                if not is_link:
                    is_link = bool(
                        getattr(st, "st_file_attributes", 0)
                        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
                    )
                if is_link:
                    raise BackupRestoreError(
                        "Backup sources must not contain symbolic links."
                    )
                safe_name(entry.name)
                count += 1
                if entry.is_dir(follow_symlinks=False):
                    _walk(entry.path)
                elif entry.is_file(follow_symlinks=False):
                    size += st.st_size
                else:
                    raise BackupRestoreError("Backup sources must be regular files.")
                if (max_files is not None and count + 1 > max_files) or (
                    max_bytes is not None and size > max_bytes
                ):
                    raise BackupRestoreError(
                        "Backup contents exceed configured recovery limits."
                    )

    _walk(str(root))
    return size, count


def capture_preflight(backups, chosen, world, cancellation_event=None):
    from .selection import server_entries
    from .server import is_link

    root = Path(backups.server.paths.server_dir)
    names = {
        "world": f"worlds/{world}",
        "server.properties": "server.properties",
        "allowlist.json": "allowlist.json",
        "permissions.json": "permissions.json",
        "script_config": "config",
        **{name: name for name in PACK_COMPONENTS},
    }
    sources = (
        server_entries(root)
        if "server_directory" in chosen
        else [backups._safe_target(names[c]) for c in chosen if c in names]
    )
    size = count = 0
    max_files = backups.server.settings.get("backups.max_files", 1_000_000)
    max_bytes = backups.server.settings.get("backups.max_expanded_bytes", 1024**4)
    for source in sources:
        check_cancellation(cancellation_event)
        if not source.exists():
            continue
        src_size, src_count = scan_source_tree(
            source,
            cancellation_event,
            is_link_fn=is_link,
            max_files=max_files - count,
            max_bytes=max_bytes - size,
        )
        size += src_size
        count += src_count
    ensure_free_space(Path(backups._directory()), size * 5 + count * 8192)


def existing_parent(path: Path) -> Path:
    while not path.exists():
        path = path.parent
    return path


def capture_size(
    backups, world: str | None, cancellation_event=None
) -> tuple[int, int]:
    from .server import is_link

    names = [
        f"worlds/{world}" if world else "worlds",
        "server.properties",
        "allowlist.json",
        "permissions.json",
        "config",
        *PACK_COMPONENTS,
    ]
    size, count = 0, 0
    for name in names:
        root = backups._safe_target(name)
        if not root.exists():
            continue
        src_size, src_count = scan_source_tree(
            root, cancellation_event, is_link_fn=is_link
        )
        size += src_size
        count += src_count
    return size, count


def restore_capacity(
    backups, manifest, targets, cancellation_event=None, *, staged=False
) -> list[RestoreVolume]:
    if "world" in targets:
        world = Path(targets["world"]).name
    else:
        try:
            world = backups._read_world(
                Path(backups.server.paths.server_properties_path)
            )
        except Exception:
            world = None
    # A malformed current properties file does not prevent preserving raw source data.
    if "server_directory" in targets:
        paths = backups._comparison_paths(
            "server_directory",
            Path(backups.server.paths.server_dir),
            cancellation_event,
        )
        size = sum(p.stat().st_size for p in paths if p.is_file())
        files = sum(p.is_file() for p in paths)
    else:
        size, files = capture_size(backups, world, cancellation_event)
    expanded = sum(item.size for item in manifest.files)
    requests = [
        (
            "server",
            Path(backups.server.paths.server_dir),
            HEADROOM + (0 if staged else expanded * 2 + len(manifest.files) * 2048),
        ),
        # Staged tree, sequential spool, compressed payload, final archive,
        # and headroom for incompressible data during the safety capture.
        ("backups", Path(backups._directory()), size * 5 + files * 4096 + HEADROOM),
    ]
    volumes: dict[int, RestoreVolume] = {}
    for role, path, required in requests:
        anchor = existing_parent(path)
        device = anchor.stat().st_dev
        free = shutil.disk_usage(anchor).free
        previous = volumes.get(device)
        total = required + (previous.required_bytes if previous else 0)
        available = min(free, previous.available_bytes) if previous else free
        volumes[device] = RestoreVolume(
            roles=[*(previous.roles if previous else []), role],
            required_bytes=total,
            available_bytes=available,
            sufficient=available >= total,
        )
    return list(volumes.values())
