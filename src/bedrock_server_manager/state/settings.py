# src/bedrock_server_manager/state/settings.py
"""
Typed settings state model for AppState.
"""

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

    def mark_dirty(self, key: Optional[str] = None) -> None:
        self._dirty = True
        if key:
            self._dirty_keys.add(key)

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

        return obj

    def set(self, key: str, value: Any) -> None:
        """Sets a setting value using dot-notation, updating models and dirty state."""
        current_value = self.get(key)
        if current_value == value:
            return

        parts = key.split(".")
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
            "custom": self.custom,
            "plugin_settings": self.plugin_settings,
        }

    @classmethod
    def from_dict(
        cls, data: Dict[str, Any], data_dir: Optional[str] = None
    ) -> "SettingsState":
        """Reconstructs SettingsState from a dictionary (e.g. from database key/value settings)."""
        defaults = cls.create_defaults(data_dir) if data_dir else cls()
        merged = defaults.to_dict()

        # Unflatten dot-notation keys if loading flat DB records
        unflattened: Dict[str, Any] = {}
        for k, v in data.items():
            if "." in k:
                parts = k.split(".")
                curr = unflattened
                for p in parts[:-1]:
                    if isinstance(curr, dict):
                        curr = curr.setdefault(p, {})
                if isinstance(curr, dict):
                    curr[parts[-1]] = v
            else:
                unflattened[k] = v

        for k, v in unflattened.items():
            if isinstance(v, dict) and k in merged and isinstance(merged[k], dict):
                merged[k].update(v)
            else:
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
