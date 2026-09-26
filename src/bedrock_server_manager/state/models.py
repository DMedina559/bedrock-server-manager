# src/bedrock_server_manager/state/models.py
"""
Typed domain state models for ServerState, PluginState, UserState, and RuntimeState.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, PrivateAttr

from ..plugins.runtime import PluginRuntime


class ServerConfigState(BaseModel):
    server_name: str
    installed_version: str = "UNKNOWN"
    status: str = "UNKNOWN"
    autoupdate: bool = False
    autostart: bool = False
    target_version: str = "UNKNOWN"
    custom: Dict[str, Any] = Field(default_factory=dict)


class ServerState(BaseModel):
    servers: Dict[str, ServerConfigState] = Field(default_factory=dict)
    _dirty: bool = PrivateAttr(default=False)
    _dirty_servers: set[str] = PrivateAttr(default_factory=set)

    def mark_dirty(self, server_name: Optional[str] = None) -> None:
        self._dirty = True
        if server_name:
            self._dirty_servers.add(server_name)

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
        return self.servers.get(server_name)

    def set(self, config: ServerConfigState) -> None:
        self.servers[config.server_name] = config
        self.mark_dirty(config.server_name)


class PluginInfoState(BaseModel):
    plugin_name: str
    enabled: bool = False
    version: Optional[str] = None
    author: Optional[str] = None
    description: Optional[str] = None
    settings: Dict[str, Any] = Field(default_factory=dict)


class PluginState(BaseModel):
    plugins: Dict[str, PluginInfoState] = Field(default_factory=dict)
    _dirty: bool = PrivateAttr(default=False)
    _dirty_plugins: set[str] = PrivateAttr(default_factory=set)

    def mark_dirty(self, plugin_name: Optional[str] = None) -> None:
        self._dirty = True
        if plugin_name:
            self._dirty_plugins.add(plugin_name)

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
        return self.plugins.get(plugin_name)

    def set(self, plugin: PluginInfoState) -> None:
        self.plugins[plugin.plugin_name] = plugin
        self.mark_dirty(plugin.plugin_name)


class UserInfoState(BaseModel):
    id: Optional[int] = None
    username: str
    role: str = "user"
    theme: str = "default"
    is_active: bool = True
    full_name: Optional[str] = None
    email: Optional[str] = None


class UserState(BaseModel):
    users: Dict[str, UserInfoState] = Field(default_factory=dict)
    _dirty: bool = PrivateAttr(default=False)
    _dirty_users: set[str] = PrivateAttr(default_factory=set)

    def mark_dirty(self, username: Optional[str] = None) -> None:
        self._dirty = True
        if username:
            self._dirty_users.add(username)

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
        return self.users.get(username)

    def set(self, user: UserInfoState) -> None:
        self.users[user.username] = user
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


class RuntimeState(BaseModel):
    servers: Dict[str, ServerRuntimeInfo] = Field(default_factory=dict)
    plugins: Dict[str, PluginRuntime] = Field(default_factory=dict)
    active_tasks: Dict[str, Any] = Field(default_factory=dict)
    websocket_connections: int = 0

    def get_server_runtime(self, server_name: str) -> ServerRuntimeInfo:
        if server_name not in self.servers:
            self.servers[server_name] = ServerRuntimeInfo()
        return self.servers[server_name]

    def set_server_runtime(self, server_name: str, runtime: ServerRuntimeInfo) -> None:
        self.servers[server_name] = runtime

    def get_plugin_runtime(self, plugin_name: str) -> PluginRuntime:
        if plugin_name not in self.plugins:
            self.plugins[plugin_name] = PluginRuntime(plugin_name=plugin_name)
        return self.plugins[plugin_name]

    def set_plugin_runtime(self, plugin_name: str, runtime: PluginRuntime) -> None:
        self.plugins[plugin_name] = runtime
