"""Conservative restore capacity estimates grouped by physical filesystem."""

import shutil
from pathlib import Path

from .models import PACK_COMPONENTS, RestoreVolume

HEADROOM = 16 * 1024 * 1024


def existing_parent(path: Path) -> Path:
    while not path.exists():
        path = path.parent
    return path


def capture_size(backups, world: str | None) -> tuple[int, int]:
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
        backups._check_tree(root)
        paths = root.rglob("*") if root.is_dir() else [root]
        for item in paths:
            if item.is_file():
                size += item.stat().st_size
                count += 1
    return size, count


def restore_capacity(
    backups, manifest, targets, *, staged=False
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
            "server_directory", Path(backups.server.paths.server_dir)
        )
        size = sum(p.stat().st_size for p in paths if p.is_file())
        files = sum(p.is_file() for p in paths)
    else:
        size, files = capture_size(backups, world)
    expanded = sum(item.size for item in manifest.files)
    requests = [
        (
            "server",
            Path(backups.server.paths.server_dir),
            HEADROOM + (0 if staged else expanded * 2 + len(manifest.files) * 2048),
        ),
        ("backups", Path(backups._directory()), size * 4 + files * 4096 + HEADROOM),
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
