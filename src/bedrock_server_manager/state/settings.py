# src/bedrock_server_manager/state/settings.py
"""
Typed settings state model for AppState.
"""

import asyncio
import copy
import logging
import os
import time
from typing import Any, Dict, Optional, Set

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    PrivateAttr,
    TypeAdapter,
    field_validator,
)

from ..diagnostics.models import DiagnosticOptions
from ..error import ConfigurationError
from ..events.models import EventOptions
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


class GeneralSettings(SettingsRecord):
    timezone: str = "UTC"

    @field_validator("timezone")
    @classmethod
    def known_timezone(cls, value: str) -> str:
        from zoneinfo import ZoneInfoNotFoundError

        from ..utils.timezones import resolve_timezone

        try:
            resolve_timezone(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError(
                "Choose a valid IANA timezone, such as America/Los_Angeles"
            ) from None
        return value


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
    app_metrics_interval_sec: int = Field(default=3, ge=1, le=3600)
    bedrock_metrics_interval_sec: int = Field(default=3, ge=1, le=3600)


DEFAULT_CORS_ORIGINS = (
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)


class WebSettings(SettingsRecord):
    cors_origins: tuple[str, ...] = DEFAULT_CORS_ORIGINS
    outbound_queue_limit: int = Field(default=64, ge=1, le=10000)
    forwarded_allow_ips: str = "127.0.0.1"
    host: str = "127.0.0.1"
    port: int = Field(default=11325, ge=1, le=65535)
    token_expires_weeks: int = Field(default=4, gt=0)
    jwt_secret_key: Optional[str] = None

    @field_validator("cors_origins", mode="before")
    @classmethod
    def origins_from_json(cls, value: Any) -> Any:
        # Store immutable state while accepting ordinary JSON arrays at the API.
        return tuple(value) if isinstance(value, list) else value

    @field_validator("cors_origins")
    @classmethod
    def validate_origins(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        origins = []
        adapter = TypeAdapter(AnyHttpUrl)
        for value in values:
            if value in ("*", "null"):
                origin = value
            else:
                url = adapter.validate_python(value)
                if (
                    url.username is not None
                    or url.password is not None
                    or url.query is not None
                    or url.fragment is not None
                    or url.path not in (None, "/")
                ):
                    raise ValueError(
                        "CORS origins must not contain credentials, paths, queries, or fragments"
                    )
                origin = str(url).rstrip("/")
            if origin not in origins:
                origins.append(origin)
        return tuple(origins)


class LifecycleSettings(SettingsRecord):
    server_stop_timeout_seconds: float = Field(default=10.0, gt=0, le=600)
    startup_timeout_seconds: float = Field(default=30.0, gt=0, le=600)
    shutdown_timeout_seconds: float = Field(default=15.0, gt=0, le=600)
    task_drain_timeout_seconds: float = Field(default=30.0, gt=0, le=600)
    plugin_timeout_seconds: float = Field(default=10.0, gt=0, le=600)
    cancellation_grace_seconds: float = Field(default=2.0, gt=0, le=30)
    request_drain_timeout_seconds: float = Field(default=10.0, gt=0, le=600)


class BackupDestination(SettingsRecord):
    path: str = Field(min_length=1)
    enabled: bool = True
    keep_count: int = Field(default=0, ge=0)
    storage_budget_bytes: int = Field(default=0, ge=0)
    min_free_bytes: int = Field(default=1073741824, ge=0)


class BackupSchedule(SettingsRecord):
    enabled: bool = True
    time: str = Field(default="03:00", pattern=r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$")
    timezone: str = "UTC"
    weekdays: list[int] = Field(
        default_factory=lambda: list(range(7)), min_length=1, max_length=7
    )
    catch_up: bool = True
    stagger_minutes: int = Field(default=15, ge=0, le=120)

    @field_validator("timezone")
    @classmethod
    def known_timezone(cls, value):
        from zoneinfo import ZoneInfoNotFoundError

        from ..utils.timezones import resolve_timezone

        try:
            resolve_timezone(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Choose a valid IANA timezone") from None
        return value

    @field_validator("weekdays")
    @classmethod
    def valid_weekdays(cls, value):
        if len(set(value)) != len(value) or any(day < 0 or day > 6 for day in value):
            raise ValueError("Weekdays must be unique integers from 0 through 6")
        return value


class ScheduledTask(BackupSchedule):
    task: str = Field(
        pattern=r"^(backup|verify|[a-zA-Z0-9_.-]+:[a-zA-Z0-9_.-]+)$", max_length=160
    )
    server_name: str = Field(min_length=1, max_length=160)
    options: dict[str, JsonValue] = Field(default_factory=dict)


class BackupSettings(SettingsRecord):
    readiness_max_age_hours: int = Field(default=48, ge=1, le=8760)
    recovery_drill_interval_hours: int = Field(default=0, ge=0, le=8760)
    encryption: bool = False
    include_server_packs: bool = True
    schedules: dict[str, BackupSchedule] = Field(default_factory=dict)
    verify_after_create: bool = False
    verification_interval_hours: int = Field(default=0, ge=0, le=8760)
    safety_window_hours: int = Field(default=168, ge=1, le=8760)
    keep_daily: int = Field(default=0, ge=0, le=365)
    keep_weekly: int = Field(default=0, ge=0, le=520)
    keep_monthly: int = Field(default=0, ge=0, le=120)
    storage_budget_bytes: int = Field(default=0, ge=0)
    destinations: dict[str, BackupDestination] = Field(default_factory=dict)
    max_files: int = Field(default=1_000_000, ge=1, le=1_000_000)
    max_expanded_bytes: int = Field(default=1024**4, ge=1)
    max_archive_bytes: int = Field(default=1024**4, ge=1)


class SettingsState(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        validate_assignment=True,
        validate_default=True,
        allow_inf_nan=False,
        revalidate_instances="always",
    )
    general: GeneralSettings = Field(default_factory=GeneralSettings)
    paths: PathsSettings = Field(default_factory=PathsSettings)
    retention: RetentionSettings = Field(default_factory=RetentionSettings)
    backups: BackupSettings = Field(default_factory=BackupSettings)
    monitoring: MonitoringSettings = Field(default_factory=MonitoringSettings)
    web: WebSettings = Field(default_factory=WebSettings)
    lifecycle: LifecycleSettings = Field(default_factory=LifecycleSettings)
    diagnostics: DiagnosticOptions = Field(default_factory=DiagnosticOptions)
    events: EventOptions = Field(default_factory=EventOptions)
    custom: Dict[str, JsonValue] = Field(default_factory=dict)
    plugin_settings: Dict[str, Dict[str, JsonValue]] = Field(default_factory=dict)

    _dirty: bool = PrivateAttr(default=False)
    _dirty_since: float | None = PrivateAttr(default=None)
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
        if not self._dirty:
            self._dirty_since = time.monotonic()
        self._dirty = True
        if key:
            self._dirty_keys.add(key)

    def remove_dirty_key(self, key: str) -> None:
        self._dirty_keys.discard(key)
        if not self._dirty_keys:
            self._dirty = False
            self._dirty_since = None

    def clear_dirty(self) -> None:
        self._dirty = False
        self._dirty_since = None
        self._dirty_keys.clear()

    @property
    def dirty_age_seconds(self) -> float | None:
        return (
            max(0, time.monotonic() - self._dirty_since)
            if self._dirty_since is not None
            else None
        )

    @property
    def is_dirty(self) -> bool:
        return self._dirty

    @property
    def dirty_keys(self) -> Set[str]:
        return set(self._dirty_keys)

    @classmethod
    def create_defaults(cls, data_dir: str) -> "SettingsState":
        """Create a default SettingsState instance configured for a given data directory."""
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
        """Return a setting value using dot-notation for nested access."""
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
        """Export settings state into a dictionary matching database key/value structure."""
        return {
            "general": self.general.model_dump(),
            "paths": self.paths.model_dump(),
            "retention": self.retention.model_dump(),
            "backups": self.backups.model_dump(),
            "monitoring": self.monitoring.model_dump(),
            "web": self.web.model_dump(mode="json", exclude_none=True),
            "lifecycle": self.lifecycle.model_dump(),
            "diagnostics": self.diagnostics.model_dump(),
            "custom": copy.deepcopy(self.custom),
            "plugin_settings": copy.deepcopy(self.plugin_settings),
        }

    @classmethod
    def from_dict(
        cls, data: Dict[str, Any], data_dir: Optional[str] = None
    ) -> "SettingsState":
        """Reconstructs SettingsState from a dictionary (e.g. from database key/value settings)."""
        data = copy.deepcopy(data)
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

        # Older 3.x databases retained removed fields inside section JSON rows.
        # Normalize after unflattening so legacy dotted rows are handled too.
        # Keep this allowlist at the load boundary; updates remain strict.
        removed_fields = {
            "paths": ("logs",),
            "retention": ("logs",),
            "web": ("threads",),
        }
        for section, removed_names in removed_fields.items():
            values = merged.get(section)
            if isinstance(values, dict):
                for name in removed_names:
                    if name in values:
                        values.pop(name)
                        logger.warning(
                            "Ignoring removed legacy setting %s.%s", section, name
                        )

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
                "app_metrics_interval_sec",
                "bedrock_metrics_interval_sec",
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
