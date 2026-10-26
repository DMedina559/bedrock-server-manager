"""Supported plugin file access scoped to an owner-specific configuration tree."""

from pathlib import Path

from ..backups.archive import safe_name
from ..backups.credentials import atomic_json
from ..error import UserInputError


def plugin_path(config_dir: str, plugin_name: str, filename: str = "") -> Path:
    safe_name(plugin_name)
    if Path(plugin_name).name != plugin_name:
        raise UserInputError("Invalid plugin identifier.")
    base = Path(config_dir) / "config" / "plugins" / plugin_name
    target = base / safe_name(filename) if filename else base
    root = Path(config_dir).resolve()
    if target.resolve() != root / "config" / "plugins" / plugin_name / filename:
        raise UserInputError("Plugin paths must not follow symbolic links.")
    return target


def read_plugin_json(config_dir: str, plugin_name: str, filename: str):
    import json

    return json.loads(plugin_path(config_dir, plugin_name, filename).read_bytes())


def write_plugin_json(config_dir: str, plugin_name: str, filename: str, value) -> None:
    target = plugin_path(config_dir, plugin_name, filename)
    target.parent.mkdir(parents=True, exist_ok=True)
    atomic_json(target, value)
