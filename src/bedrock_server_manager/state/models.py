# src/bedrock_server_manager/state/models.py
"""
Typed domain state models for ServerState, PluginState, UserState, and RuntimeState.
"""

import asyncio
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, cast

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from ..plugins.runtime import PluginRuntime


class PersistentRecord(BaseModel):
    model_config = ConfigDict(
        extra="forbid", validate_assignment=True, revalidate_instances="always"
    )


class ServerConfigState(PersistentRecord):
    server_name: str
    installed_version: str = "UNKNOWN"
    status: str = "UNKNOWN"
    autoupdate: bool = False
    autostart: bool = False
    target_version: str = "UNKNOWN"
    custom: Dict[str, JsonValue] = Field(default_factory=dict)


@dataclass
class ServerState:
    servers: Dict[str, ServerConfigState] = field(default_factory=dict)
    _dirty: bool = field(default=False, init=False, repr=False)
    _dirty_servers: set[str] = field(init=False, repr=False, default_factory=set)
    _locks: Dict[str, asyncio.Lock] = field(
        init=False, repr=False, default_factory=dict
    )

    def get_lock(self, server_name: str) -> asyncio.Lock:
        if server_name not in self._locks:
            self._locks[server_name] = asyncio.Lock()
        return self._locks[server_name]

    def mark_dirty(self, server_name: Optional[str] = None) -> None:
        self._dirty = True
        if server_name:
            self._dirty_servers.add(server_name)

    def remove_dirty_server(self, server_name: str) -> None:
        self._dirty_servers.discard(server_name)
        if not self._dirty_servers:
            self._dirty = False

    def clear_dirty(self) -> None:
        self._dirty = False
        self._dirty_servers.clear()

    @property
    def is_dirty(self) -> bool:
        return self._dirty

    @property
    def dirty_servers(self) -> set[str]:
        return set(self._dirty_servers)

    def get(self, server_name: str) -> Optional[ServerConfigState]:
        cfg = self.servers.get(server_name)
        return cfg.model_copy(deep=True) if cfg is not None else None

    def set(self, config: ServerConfigState) -> None:
        self.servers[config.server_name] = ServerConfigState.model_validate(
            config
        ).model_copy(deep=True)
        self.mark_dirty(config.server_name)


class PluginInfoState(PersistentRecord):
    plugin_name: str
    enabled: bool = False
    version: Optional[str] = None
    author: Optional[str] = None
    description: Optional[str] = None


@dataclass
class PluginState:
    plugins: Dict[str, PluginInfoState] = field(default_factory=dict)
    _dirty: bool = field(default=False, init=False, repr=False)
    _dirty_plugins: set[str] = field(init=False, repr=False, default_factory=set)
    _locks: Dict[str, asyncio.Lock] = field(
        init=False, repr=False, default_factory=dict
    )

    def get_lock(self, plugin_name: str) -> asyncio.Lock:
        if plugin_name not in self._locks:
            self._locks[plugin_name] = asyncio.Lock()
        return self._locks[plugin_name]

    def mark_dirty(self, plugin_name: Optional[str] = None) -> None:
        self._dirty = True
        if plugin_name:
            self._dirty_plugins.add(plugin_name)

    def remove_dirty_plugin(self, plugin_name: str) -> None:
        self._dirty_plugins.discard(plugin_name)
        if not self._dirty_plugins:
            self._dirty = False

    def clear_dirty(self) -> None:
        self._dirty = False
        self._dirty_plugins.clear()

    @property
    def is_dirty(self) -> bool:
        return self._dirty

    @property
    def dirty_plugins(self) -> set[str]:
        return set(self._dirty_plugins)

    def get(self, plugin_name: str) -> Optional[PluginInfoState]:
        p_info = self.plugins.get(plugin_name)
        return p_info.model_copy(deep=True) if p_info is not None else None

    def set(self, plugin: PluginInfoState) -> None:
        self.plugins[plugin.plugin_name] = PluginInfoState.model_validate(
            plugin
        ).model_copy(deep=True)
        self.mark_dirty(plugin.plugin_name)


class UserInfoState(PersistentRecord):
    id: Optional[int] = None
    username: str
    role: str = "user"
    theme: str = "default"
    is_active: bool = True
    full_name: Optional[str] = None
    email: Optional[str] = None


@dataclass
class UserState:
    users: Dict[str, UserInfoState] = field(default_factory=dict)
    _dirty: bool = field(default=False, init=False, repr=False)
    _dirty_users: set[str] = field(init=False, repr=False, default_factory=set)
    _locks: Dict[str, asyncio.Lock] = field(
        init=False, repr=False, default_factory=dict
    )

    def get_lock(self, username: str) -> asyncio.Lock:
        if username not in self._locks:
            self._locks[username] = asyncio.Lock()
        return self._locks[username]

    def mark_dirty(self, username: Optional[str] = None) -> None:
        self._dirty = True
        if username:
            self._dirty_users.add(username)

    def remove_dirty_user(self, username: str) -> None:
        self._dirty_users.discard(username)
        if not self._dirty_users:
            self._dirty = False

    def clear_dirty(self) -> None:
        self._dirty = False
        self._dirty_users.clear()

    @property
    def is_dirty(self) -> bool:
        return self._dirty

    @property
    def dirty_users(self) -> set[str]:
        return set(self._dirty_users)

    def get(self, username: str) -> Optional[UserInfoState]:
        u_info = self.users.get(username)
        return u_info.model_copy(deep=True) if u_info is not None else None

    def set(self, user: UserInfoState) -> None:
        self.users[user.username] = UserInfoState.model_validate(user).model_copy(
            deep=True
        )
        self.mark_dirty(user.username)


class BanItem(BaseModel):
    player_name: str
    xuid: str
    reason: Optional[str] = None
    banned_at: Optional[str] = None


class BanResult(BaseModel):
    success: bool
    message: str
    bans: Optional[List[BanItem]] = None


class ServerRuntimeInfo(BaseModel):
    running: bool = False
    pid: Optional[int] = None
    players_online: int = 0
    online_players_list: List[str] = Field(default_factory=list)
    cpu_percent: float = 0.0
    memory_mb: float = 0.0


@dataclass
class RuntimeState:
    servers: Dict[str, ServerRuntimeInfo] = field(default_factory=dict)
    plugins: Dict[str, PluginRuntime] = field(default_factory=dict)
    active_tasks: Dict[str, Any] = field(default_factory=dict)
    websocket_connections: int = 0

    def get_server_runtime(self, server_name: str) -> ServerRuntimeInfo:
        if server_name not in self.servers:
            self.servers[server_name] = ServerRuntimeInfo()
        return cast(ServerRuntimeInfo, self.servers[server_name].model_copy(deep=True))

    def set_server_runtime(self, server_name: str, runtime: ServerRuntimeInfo) -> None:
        self.servers[server_name] = runtime.model_copy(deep=True)

    def get_plugin_runtime(self, plugin_name: str) -> PluginRuntime:
        if plugin_name not in self.plugins:
            self.plugins[plugin_name] = PluginRuntime(plugin_name=plugin_name)
        return cast(PluginRuntime, deepcopy(self.plugins[plugin_name]))

    def set_plugin_runtime(self, plugin_name: str, runtime: PluginRuntime) -> None:
        self.plugins[plugin_name] = deepcopy(runtime)
