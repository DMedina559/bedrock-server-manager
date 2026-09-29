# src/bedrock_server_manager/state/settings.py
"""
Typed settings state model for AppState.
"""

import asyncio
import copy
import logging
import os
from typing import Any, Dict, Optional, Set

from pydantic import BaseModel, Field, PrivateAttr

from ..error import ConfigurationError

logger = logging.getLogger(__name__)


class PathsSettings(BaseModel):
    servers: str = ""
    content: str = ""
    downloads: str = ""
    backups: str = ""
    plugins: str = ""
    themes: str = ""


class RetentionSettings(BaseModel):
    backups: int = 3
    downloads: int = 3


class MonitoringSettings(BaseModel):
    max_retries: int = 3
    process_interval_sec: int = 10
    player_interval_sec: int = 10


class WebSettings(BaseModel):
    host: str = "127.0.0.1"
    port: int = 11325
    token_expires_weeks: int = 4
    jwt_secret_key: Optional[str] = None


class SettingsState(BaseModel):
    paths: PathsSettings = Field(default_factory=PathsSettings)
    retention: RetentionSettings = Field(default_factory=RetentionSettings)
    monitoring: MonitoringSettings = Field(default_factory=MonitoringSettings)
    web: WebSettings = Field(default_factory=WebSettings)
    custom: Dict[str, Any] = Field(default_factory=dict)
    plugin_settings: Dict[str, Dict[str, Any]] = Field(default_factory=dict)

    _dirty: bool = PrivateAttr(default=False)
    _dirty_keys: Set[str] = PrivateAttr(default_factory=set)
    _locks: Dict[str, asyncio.Lock] = PrivateAttr(default_factory=dict)

    def get_lock(self, key: str = "global") -> asyncio.Lock:
        root_key = key.split(".")[0]
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
            not hasattr(self, root_key)
            and root_key not in self.custom
            and root_key not in self.plugin_settings
        ):
            return default

        obj: Any = getattr(self, root_key, None)
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
                if hasattr(obj, part):
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

    def set(self, key: str, value: Any) -> None:
        """Sets a setting value using dot-notation, updating models and dirty state."""
        parts = key.split(".")
        for part in parts:
            if part.startswith("_") or "__" in part:
                raise ConfigurationError(
                    f"Access to private/dunder key '{key}' is forbidden."
                )

        current_value = self.get(key)
        if current_value == value:
            return

        root_key = parts[0]

        if hasattr(self, root_key):
            root_attr = getattr(self, root_key)
            if isinstance(root_attr, BaseModel):
                if len(parts) == 2 and hasattr(root_attr, parts[1]):
                    setattr(root_attr, parts[1], value)
                else:
                    # Deep nested dict or custom updates on sub-model
                    sub_dict = root_attr.model_dump()
                    curr = sub_dict
                    for p in parts[1:-1]:
                        if not isinstance(curr, dict) or (
                            p in curr and not isinstance(curr[p], dict)
                        ):
                            raise ConfigurationError(
                                f"Cannot set key '{key}' because path conflict."
                            )
                        curr = curr.setdefault(p, {})
                    if not isinstance(curr, dict):
                        raise ConfigurationError(
                            f"Cannot set key '{key}' because path conflict."
                        )
                    curr[parts[-1]] = value
                    new_sub_model = type(root_attr)(**sub_dict)
                    setattr(self, root_key, new_sub_model)
            elif isinstance(root_attr, dict):
                curr = root_attr
                for p in parts[1:-1]:
                    if not isinstance(curr, dict) or (
                        p in curr and not isinstance(curr[p], dict)
                    ):
                        raise ConfigurationError(
                            f"Cannot set key '{key}' because path conflict."
                        )
                    curr = curr.setdefault(p, {})
                if not isinstance(curr, dict):
                    raise ConfigurationError(
                        f"Cannot set key '{key}' because path conflict."
                    )
                curr[parts[-1]] = value
        else:
            # Belongs in custom settings
            curr = self.custom
            for p in parts[:-1]:
                if not isinstance(curr, dict) or (
                    p in curr and not isinstance(curr[p], dict)
                ):
                    raise ConfigurationError(
                        f"Cannot set key '{key}' because path conflict."
                    )
                curr = curr.setdefault(p, {})
            if not isinstance(curr, dict):
                raise ConfigurationError(
                    f"Cannot set key '{key}' because path conflict."
                )
            curr[parts[-1]] = value

        self.mark_dirty(root_key)

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

        inst = cls(
            paths=PathsSettings(**merged.get("paths", {})),
            retention=RetentionSettings(**merged.get("retention", {})),
            monitoring=MonitoringSettings(**merged.get("monitoring", {})),
            web=WebSettings(**merged.get("web", {})),
            custom=merged.get("custom", {}),
            plugin_settings=merged.get("plugin_settings", {}),
        )
        return inst
