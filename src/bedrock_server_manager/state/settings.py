# src/bedrock_server_manager/state/settings.py
"""
Typed settings state model for AppState.
"""

import asyncio
import copy
import logging
import os
from typing import Any, Dict, Optional, Set

from pydantic import BaseModel, ConfigDict, Field, JsonValue, PrivateAttr, TypeAdapter

from ..error import ConfigurationError
from .validation import json_equal

logger = logging.getLogger(__name__)


class SettingsRecord(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
        validate_default=True,
        allow_inf_nan=False,
        revalidate_instances="always",
    )


class PathsSettings(SettingsRecord):
    servers: str = ""
    content: str = ""
    downloads: str = ""
    backups: str = ""
    plugins: str = ""
    themes: str = ""


class RetentionSettings(SettingsRecord):
    backups: int = Field(default=3, ge=0)
    downloads: int = Field(default=3, ge=0)


class MonitoringSettings(SettingsRecord):
    max_retries: int = Field(default=3, ge=0)
    process_interval_sec: int = Field(default=10, gt=0)
    player_interval_sec: int = Field(default=10, gt=0)


class WebSettings(SettingsRecord):
    host: str = "127.0.0.1"
    port: int = Field(default=11325, ge=1, le=65535)
    token_expires_weeks: int = Field(default=4, gt=0)
    jwt_secret_key: Optional[str] = None


class SettingsState(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        validate_assignment=True,
        validate_default=True,
        allow_inf_nan=False,
        revalidate_instances="always",
    )
    paths: PathsSettings = Field(default_factory=PathsSettings)
    retention: RetentionSettings = Field(default_factory=RetentionSettings)
    monitoring: MonitoringSettings = Field(default_factory=MonitoringSettings)
    web: WebSettings = Field(default_factory=WebSettings)
    custom: Dict[str, JsonValue] = Field(default_factory=dict)
    plugin_settings: Dict[str, Dict[str, JsonValue]] = Field(default_factory=dict)

    _dirty: bool = PrivateAttr(default=False)
    _dirty_keys: Set[str] = PrivateAttr(default_factory=set)
    _locks: Dict[str, asyncio.Lock] = PrivateAttr(default_factory=dict)

    def __getattribute__(self, name: str) -> Any:
        value = super().__getattribute__(name)
        # Public container reads are snapshots. Persist mutations through set().
        if name in {"custom", "plugin_settings"}:
            return copy.deepcopy(value)
        return value

    def __setattr__(self, name: str, value: Any) -> None:
        super().__setattr__(name, value)
        if name in type(self).model_fields and self.__pydantic_private__ is not None:
            self.mark_dirty(name)

    def get_lock(self, key: str = "global") -> asyncio.Lock:
        # Every setter validates/replaces a whole snapshot; use one shared lock.
        root_key = "global"
        if root_key not in self._locks:
            self._locks[root_key] = asyncio.Lock()
        return self._locks[root_key]

    def mark_dirty(self, key: Optional[str] = None) -> None:
        self._dirty = True
        if key:
            self._dirty_keys.add(key)

    def remove_dirty_key(self, key: str) -> None:
        self._dirty_keys.discard(key)
        if not self._dirty_keys:
            self._dirty = False

    def clear_dirty(self) -> None:
        self._dirty = False
        self._dirty_keys.clear()

    @property
    def is_dirty(self) -> bool:
        return self._dirty

    @property
    def dirty_keys(self) -> Set[str]:
        return set(self._dirty_keys)

    @classmethod
    def create_defaults(cls, data_dir: str) -> "SettingsState":
        """Creates a default SettingsState instance configured for a given data directory."""
        return cls(
            paths=PathsSettings(
                servers=os.path.join(data_dir, "servers"),
                content=os.path.join(data_dir, "content"),
                downloads=os.path.join(data_dir, ".downloads"),
                backups=os.path.join(data_dir, "backups"),
                plugins=os.path.join(data_dir, "plugins"),
                themes=os.path.join(data_dir, "themes"),
            ),
            retention=RetentionSettings(),
            monitoring=MonitoringSettings(),
            web=WebSettings(),
            custom={},
            plugin_settings={},
        )

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieves a setting value using dot-notation for nested access."""
        parts = key.split(".")
        for part in parts:
            if part.startswith("_") or "__" in part:
                raise ConfigurationError(
                    f"Access to private/dunder key '{key}' is forbidden."
                )

        root_key = parts[0]

        if (
            root_key not in type(self).model_fields
            and root_key not in self.custom
            and root_key not in self.plugin_settings
        ):
            return default

        obj: Any = (
            getattr(self, root_key, None)
            if root_key in type(self).model_fields
            else None
        )
        if obj is None and root_key in self.custom:
            obj = self.custom[root_key]
            parts = parts[1:]
        elif obj is None and root_key in self.plugin_settings:
            obj = self.plugin_settings[root_key]
            parts = parts[1:]
        else:
            parts = parts[1:]

        for part in parts:
            if isinstance(obj, BaseModel):
                if part in type(obj).model_fields:
                    obj = getattr(obj, part)
                else:
                    return default
            elif isinstance(obj, dict):
                if part in obj:
                    obj = obj[part]
                else:
                    return default
            else:
                return default

        if isinstance(obj, BaseModel):
            return obj.model_copy(deep=True)
        elif isinstance(obj, (dict, list)):
            return copy.deepcopy(obj)

        return obj

    def set(self, key: str, value: Any) -> bool:
        """Validate a complete updated snapshot before mutating live settings."""
        parts = key.split(".")
        if any(not part or part.startswith("_") or "__" in part for part in parts):
            raise ConfigurationError(f"Invalid setting key '{key}'.")
        data = self.model_dump(mode="python")
        if parts[0] in type(self).model_fields:
            target = data
            dirty_key = parts[0]
        elif parts[0] in data["custom"]:
            target = data["custom"]
            dirty_key = "custom"
        elif parts[0] in data["plugin_settings"]:
            target = data["plugin_settings"]
            dirty_key = "plugin_settings"
        else:
            target = data["custom"]
            dirty_key = "custom"
        current = target
        for part in parts[:-1]:
            child = current.setdefault(part, {})
            if not isinstance(child, dict):
                raise ConfigurationError(
                    f"Cannot set key '{key}' because path conflict."
                )
            current = child
        current[parts[-1]] = value
        updated = type(self).model_validate(data)
        if json_equal(self.to_dict(), updated.to_dict()):
            return False
        for name in type(self).model_fields:
            if name == dirty_key:
                setattr(self, name, getattr(updated, name))
        return True

    def to_dict(self) -> Dict[str, Any]:
        """Exports settings state into a dictionary matching database key/value structure."""
        return {
            "paths": self.paths.model_dump(),
            "retention": self.retention.model_dump(),
            "monitoring": self.monitoring.model_dump(),
            "web": self.web.model_dump(exclude_none=True),
            "custom": copy.deepcopy(self.custom),
            "plugin_settings": copy.deepcopy(self.plugin_settings),
        }

    @classmethod
    def from_dict(
        cls, data: Dict[str, Any], data_dir: Optional[str] = None
    ) -> "SettingsState":
        """Reconstructs SettingsState from a dictionary (e.g. from database key/value settings)."""
        defaults = cls.create_defaults(data_dir) if data_dir else cls()
        merged = defaults.to_dict()

        def _deep_merge_dicts(
            source: Dict[Any, Any], destination: Dict[Any, Any]
        ) -> Dict[Any, Any]:
            for key, value in source.items():
                if isinstance(value, dict) and isinstance(destination.get(key), dict):
                    _deep_merge_dicts(value, destination[key])
                elif value is not None or key not in destination:
                    destination[key] = value
            return destination

        # Unflatten dot-notation keys and merge all DB records into a unified structure
        unflattened: Dict[str, Any] = {}
        for k, v in data.items():
            if "." in k:
                parts = k.split(".")
                curr = unflattened
                for p in parts[:-1]:
                    if isinstance(curr, dict):
                        curr = curr.setdefault(p, {})
                if isinstance(curr, dict):
                    if isinstance(v, dict) and isinstance(curr.get(parts[-1]), dict):
                        _deep_merge_dicts(v, curr[parts[-1]])
                    elif v is not None or parts[-1] not in curr:
                        curr[parts[-1]] = v
            else:
                if isinstance(v, dict) and isinstance(unflattened.get(k), dict):
                    _deep_merge_dicts(v, unflattened[k])
                elif v is not None or k not in unflattened:
                    unflattened[k] = v

        for k, v in unflattened.items():
            if isinstance(v, dict) and k in merged and isinstance(merged[k], dict):
                _deep_merge_dicts(v, merged[k])
            elif v is not None or k not in merged:
                merged[k] = v

        monitoring = merged.get("monitoring", {})
        if "max_retiries" in monitoring:
            legacy_retries = monitoring.pop("max_retiries")
            supplied = unflattened.get("monitoring", {})
            if "max_retries" not in supplied:
                monitoring["max_retries"] = legacy_retries

        # Normalize only known legacy numeric settings at the DB load boundary.
        numeric_fields = {
            "retention": ("backups", "downloads"),
            "monitoring": (
                "max_retries",
                "process_interval_sec",
                "player_interval_sec",
            ),
            "web": ("port", "token_expires_weeks"),
        }
        integer = TypeAdapter(int)
        for section, fields in numeric_fields.items():
            if isinstance(merged.get(section), dict):
                for name in fields:
                    value = merged[section].get(name)
                    if isinstance(value, str):
                        merged[section][name] = integer.validate_python(value)

        # Old extension roots have an explicit migration into the custom namespace.
        for name in tuple(merged):
            if name not in cls.model_fields:
                logger.warning("Migrating legacy settings root %s into custom", name)
                merged["custom"].setdefault(name, merged.pop(name))
        inst = cls.model_validate(merged)
        inst.clear_dirty()
        return inst
