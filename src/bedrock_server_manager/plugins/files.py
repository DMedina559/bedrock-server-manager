"""Supported plugin file access scoped to an owner-specific configuration tree."""

import json
import os
from pathlib import Path
from typing import Any, Literal

from ..backups.archive import safe_name
from ..backups.credentials import atomic_bytes, atomic_json
from ..error import UserInputError

RESERVED_PLUGIN_DIRS = frozenset({"public", "shared", "private"})
RESERVED_PLUGIN_NAMES = RESERVED_PLUGIN_DIRS
PluginFileScope = Literal["private", "public", "shared"]
PluginFileFormat = Literal["json", "text", "bytes"]


def _resolve_scope_subdir(plugin_name: str, scope: str) -> str:
    if scope in ("public", "shared"):
        if plugin_name:
            safe_name(plugin_name)
            if (
                Path(plugin_name).name != plugin_name
                or plugin_name.lower() in RESERVED_PLUGIN_DIRS
            ):
                raise UserInputError("Invalid plugin identifier.")
        return "public"
    if scope == "private":
        safe_name(plugin_name)
        if (
            Path(plugin_name).name != plugin_name
            or plugin_name.lower() in RESERVED_PLUGIN_DIRS
        ):
            raise UserInputError("Invalid plugin identifier.")
        return plugin_name
    raise UserInputError("Invalid plugin file scope.")


def plugin_path(
    config_dir: str,
    plugin_name: str,
    filename: str = "",
    *,
    scope: PluginFileScope = "private",
) -> Path:
    subdir = _resolve_scope_subdir(plugin_name, scope)
    root_path = Path(config_dir)
    if root_path.is_symlink():
        raise UserInputError("Plugin paths must not follow symbolic links.")
    plugins_root = root_path / "plugins"
    if plugins_root.is_symlink():
        raise UserInputError("Plugin paths must not follow symbolic links.")
    base = plugins_root / subdir
    if scope == "private":
        legacy_base = root_path / "config" / "plugins" / plugin_name
        if legacy_base.exists() and not legacy_base.is_symlink() and not base.exists():
            plugins_root.mkdir(parents=True, exist_ok=True)
            try:
                os.replace(legacy_base, base)
            except OSError:
                pass
    target = base / safe_name(filename) if filename else base
    root = root_path.resolve()
    expected = (
        root / "plugins" / subdir / filename if filename else root / "plugins" / subdir
    )
    if target.resolve() != expected:
        raise UserInputError("Plugin paths must not follow symbolic links.")
    return target


def read_plugin_json(
    config_dir: str,
    plugin_name: str,
    filename: str,
    *,
    scope: PluginFileScope = "private",
) -> Any:
    return json.loads(
        plugin_path(config_dir, plugin_name, filename, scope=scope).read_bytes()
    )


def write_plugin_json(
    config_dir: str,
    plugin_name: str,
    filename: str,
    value: Any,
    *,
    scope: PluginFileScope = "private",
) -> None:
    target = plugin_path(config_dir, plugin_name, filename, scope=scope)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.resolve() != (
        Path(config_dir).resolve()
        / "plugins"
        / _resolve_scope_subdir(plugin_name, scope)
        / filename
    ):
        raise UserInputError("Plugin paths must not follow symbolic links.")
    atomic_json(target, value)


def read_plugin_content(
    config_dir: str,
    plugin_name: str,
    filename: str,
    *,
    scope: PluginFileScope = "private",
    format: PluginFileFormat = "json",
) -> Any:
    target = plugin_path(config_dir, plugin_name, filename, scope=scope)
    if format == "json":
        return json.loads(target.read_bytes())
    if format == "text":
        return target.read_text(encoding="utf-8")
    if format == "bytes":
        return target.read_bytes()
    raise UserInputError("Invalid plugin file format.")


def write_plugin_content(
    config_dir: str,
    plugin_name: str,
    filename: str,
    value: Any,
    *,
    scope: PluginFileScope = "private",
    format: PluginFileFormat = "json",
) -> None:
    if format == "json":
        write_plugin_json(config_dir, plugin_name, filename, value, scope=scope)
        return
    target = plugin_path(config_dir, plugin_name, filename, scope=scope)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.resolve() != (
        Path(config_dir).resolve()
        / "plugins"
        / _resolve_scope_subdir(plugin_name, scope)
        / filename
    ):
        raise UserInputError("Plugin paths must not follow symbolic links.")
    if format == "text":
        if not isinstance(value, str):
            raise UserInputError("Text plugin files require a string value.")
        atomic_bytes(target, value.encode("utf-8"))
        return
    if format == "bytes":
        if not isinstance(value, (bytes, bytearray)):
            raise UserInputError("Binary plugin files require bytes.")
        atomic_bytes(target, bytes(value))
        return
    raise UserInputError("Invalid plugin file format.")
