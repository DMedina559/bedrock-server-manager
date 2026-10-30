"""Conservative restore capacity estimates grouped by physical filesystem."""

import shutil
from pathlib import Path

from ..error import BackupRestoreError
from ..utils.threads import check_cancellation
from .models import PACK_COMPONENTS, RestoreVolume
from .work import tree_paths

HEADROOM = 16 * 1024 * 1024


def ensure_free_space(path: Path, required: int) -> None:
    """Fail before writing temporary data, retaining conservative headroom."""
    if shutil.disk_usage(existing_parent(path)).free < required + HEADROOM:
        raise BackupRestoreError("Insufficient space for backup staging or recovery.")


def capture_preflight(backups, chosen, world, cancellation_event=None):
    from .selection import server_entries

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
    for source in sources:
        check_cancellation(cancellation_event)
        if not source.exists():
            continue
        backups._check_tree(source, cancellation_event)
        for item in tree_paths(source, cancellation_event):
            check_cancellation(cancellation_event)
            if item.is_file():
                size += item.stat().st_size
            count += 1
            if count + 1 > backups.server.settings.get(
                "backups.max_files", 1_000_000
            ) or size > backups.server.settings.get(
                "backups.max_expanded_bytes", 1024**4
            ):
                raise BackupRestoreError(
                    "Backup contents exceed configured recovery limits."
                )
    ensure_free_space(Path(backups._directory()), size * 5 + count * 8192)


def existing_parent(path: Path) -> Path:
    while not path.exists():
        path = path.parent
    return path


def capture_size(
    backups, world: str | None, cancellation_event=None
) -> tuple[int, int]:
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
        check_cancellation(cancellation_event)
        backups._check_tree(root, cancellation_event)
        paths = tree_paths(root, cancellation_event)
        for item in paths:
            check_cancellation(cancellation_event)
            if item.is_file():
                size += item.stat().st_size
                count += 1
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
