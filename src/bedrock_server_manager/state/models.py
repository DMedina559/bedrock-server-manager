# src/bedrock_server_manager/state/models.py
"""
Typed domain state models for ServerState, PluginState, UserState, SchedulerState, and RuntimeState.
"""

import asyncio
import json
import time
from copy import deepcopy
from dataclasses import dataclass, field
from typing import (
    Any,
    ClassVar,
    Dict,
    Generic,
    List,
    Literal,
    Optional,
    Self,
    TypeVar,
    cast,
)

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from .maintenance import MaintenanceGuard

UserRole = Literal["admin", "moderator", "user"]


def json_equal(left: object, right: object) -> bool:
    """Compare validated JSON snapshots without Python's bool/int equality alias."""
    return json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(
        right, sort_keys=True, allow_nan=False
    )


class PersistentRecord(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        hide_input_in_errors=True,
        strict=True,
        validate_assignment=True,
        validate_default=True,
        allow_inf_nan=False,
        revalidate_instances="always",
    )


T = TypeVar("T", bound=PersistentRecord)


@dataclass
class EntityStateMap(Generic[T]):
    _model_type: ClassVar[type[PersistentRecord]]
    _key_field: ClassVar[str]

    _items: Dict[str, T] = field(default_factory=dict)
    _dirty: bool = field(default=False, init=False, repr=False)
    _dirty_since: float | None = field(default=None, init=False, repr=False)
    _dirty_keys: set[str] = field(init=False, repr=False, default_factory=set)
    _locks: Dict[str, asyncio.Lock] = field(
        init=False, repr=False, default_factory=dict
    )

    @property
    def count(self) -> int:
        return len(self._items)

    def _snapshots(self) -> Dict[str, T]:
        return {
            name: value.model_copy(deep=True) for name, value in self._items.items()
        }

    def replace_loaded(self, values: Dict[str, T]) -> None:
        model_cls = cast(type[T], self._model_type)
        self._items = {
            name: model_cls.model_validate(value).model_copy(deep=True)
            for name, value in values.items()
        }

    def remove(self, name: str) -> None:
        self._items.pop(name, None)
        self.remove_dirty(name)

    def get_lock(self, name: str) -> asyncio.Lock:
        if name not in self._locks:
            self._locks[name] = asyncio.Lock()
        return self._locks[name]

    def mark_dirty(self, name: Optional[str] = None) -> None:
        if not self._dirty:
            self._dirty_since = time.monotonic()
        self._dirty = True
        if name:
            self._dirty_keys.add(name)

    def remove_dirty(self, name: str) -> None:
        self._dirty_keys.discard(name)
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
    def dirty_keys(self) -> set[str]:
        return set(self._dirty_keys)

    def get(self, name: str) -> Optional[T]:
        item = self._items.get(name)
        return item.model_copy(deep=True) if item is not None else None

    def set(self, item: T) -> None:
        model_cls = cast(type[T], self._model_type)
        validated = model_cls.model_validate(item).model_copy(deep=True)
        key = str(getattr(validated, self._key_field))
        self._items[key] = validated
        self.mark_dirty(key)


class ServerConfigState(PersistentRecord):
    server_name: str
    installed_version: str = "UNKNOWN"
    status: str = "UNKNOWN"
    autoupdate: bool = False
    autostart: bool = False
    target_version: str = "UNKNOWN"
    custom: Dict[str, JsonValue] = Field(default_factory=dict)


@dataclass
class ServerState(EntityStateMap[ServerConfigState]):
    _model_type: ClassVar[type[PersistentRecord]] = ServerConfigState
    _key_field: ClassVar[str] = "server_name"
    _maintenance: Dict[str, MaintenanceGuard] = field(
        default_factory=dict, init=False, repr=False
    )

    @property
    def servers(self) -> Dict[str, ServerConfigState]:
        """Read-only snapshots; use set() and remove() to mutate live state."""
        return self._snapshots()

    @property
    def dirty_servers(self) -> set[str]:
        return self.dirty_keys

    def remove_dirty_server(self, server_name: str) -> None:
        self.remove_dirty(server_name)

    def maintenance(self, server_name: str) -> MaintenanceGuard:
        return self._maintenance.setdefault(server_name, MaintenanceGuard())


class PluginInfoState(PersistentRecord):
    plugin_name: str
    enabled: bool = False
    version: Optional[str] = None
    author: Optional[str] = None
    description: Optional[str] = None


@dataclass
class PluginState(EntityStateMap[PluginInfoState]):
    _model_type: ClassVar[type[PersistentRecord]] = PluginInfoState
    _key_field: ClassVar[str] = "plugin_name"

    @property
    def plugins(self) -> Dict[str, PluginInfoState]:
        """Read-only snapshots; use set() and remove() to mutate live state."""
        return self._snapshots()

    @property
    def dirty_plugins(self) -> set[str]:
        return self.dirty_keys

    def remove_dirty_plugin(self, plugin_name: str) -> None:
        self.remove_dirty(plugin_name)


class UserInfoState(PersistentRecord):
    id: Optional[int] = None
    username: str
    role: UserRole = "user"
    theme: str = "default"
    is_active: bool = True
    full_name: Optional[str] = None
    email: Optional[str] = None


@dataclass
class UserState(EntityStateMap[UserInfoState]):
    _model_type: ClassVar[type[PersistentRecord]] = UserInfoState
    _key_field: ClassVar[str] = "username"

    @property
    def users(self) -> Dict[str, UserInfoState]:
        """Read-only snapshots; use set() and remove() to mutate live state."""
        return self._snapshots()

    @property
    def dirty_users(self) -> set[str]:
        return self.dirty_keys

    def remove_dirty_user(self, username: str) -> None:
        self.remove_dirty(username)


@dataclass
class SchedulerState:
    """Committed scheduler read model; all writes go through Storage transactions."""

    _records: dict[str, tuple[dict[str, Any], dict[str, Any], str | None]] = field(
        default_factory=dict, repr=False
    )

    @property
    def count(self) -> int:
        return len(self._records)

    @property
    def records(self):
        return deepcopy(self._records)

    def replace_loaded(self, rows) -> None:
        self._records = {
            name: deepcopy((configuration, state, legacy))
            for name, configuration, state, legacy in rows
        }

    def update_loaded(self, names, rows):
        for name in names:
            self._records.pop(name, None)
        self._records.update(
            {
                name: deepcopy((config, state, legacy))
                for name, config, state, legacy in rows
            }
        )


class BanItem(PersistentRecord):
    player_name: str
    xuid: str
    reason: Optional[str] = None
    banned_at: Optional[str] = None


class RuntimePlayer(PersistentRecord):
    name: str
    xuid: str


class ServerRuntimeInfo(PersistentRecord):
    running: bool = False
    pid: Optional[int] = Field(default=None, gt=0)
    players_available: bool = True
    players_online: int = Field(default=0, ge=0)
    players: List[RuntimePlayer] = Field(default_factory=list)
    cpu_percent: float = Field(default=0.0, ge=0)
    memory_mb: float = Field(default=0.0, ge=0)

    @model_validator(mode="after")
    def coherent_runtime(self) -> Self:
        if self.players_online != len(self.players):
            raise ValueError("Player count must match the player list.")
        if not self.running and self.pid is not None:
            raise ValueError("Stopped servers cannot retain a process ID.")
        return self


@dataclass
class RuntimeState:
    scheduler: dict[str, JsonValue] = field(default_factory=dict)
    _servers: Dict[str, ServerRuntimeInfo] = field(default_factory=dict)

    @property
    def servers(self) -> Dict[str, ServerRuntimeInfo]:
        return {
            name: value.model_copy(deep=True) for name, value in self._servers.items()
        }

    def get_server_runtime(self, server_name: str) -> ServerRuntimeInfo:
        if server_name not in self._servers:
            self._servers[server_name] = ServerRuntimeInfo()
        return cast(ServerRuntimeInfo, self._servers[server_name].model_copy(deep=True))

    def set_server_runtime(self, server_name: str, runtime: ServerRuntimeInfo) -> None:
        self._servers[server_name] = ServerRuntimeInfo.model_validate(
            runtime
        ).model_copy(deep=True)

    def update_server_runtime(self, server_name: str, **values: object) -> None:
        """Validate and publish one complete runtime update without exposing handles."""
        data = self.get_server_runtime(server_name).model_dump()
        data.update(values)
        if values.get("running") is False:
            data.update(
                pid=None,
                players_available=True,
                players_online=0,
                players=[],
                cpu_percent=0.0,
                memory_mb=0.0,
            )
        record = ServerRuntimeInfo.model_validate(data)
        self.set_server_runtime(server_name, record)

    def remove_server_runtime(self, server_name: str) -> None:
        self._servers.pop(server_name, None)
