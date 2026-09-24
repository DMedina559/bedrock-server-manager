# src/bedrock_server_manager/state/models.py
"""
Typed domain state models for ServerState, PluginState, UserState, and RuntimeState.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, PrivateAttr


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
    name: str
    version: str
    enabled: bool = True
    manifest: Dict[str, Any] = Field(default_factory=dict)
    settings: Dict[str, Any] = Field(default_factory=dict)


class PluginState(BaseModel):
    plugins: Dict[str, PluginInfoState] = Field(default_factory=dict)
    _dirty: bool = PrivateAttr(default=False)

    def mark_dirty(self) -> None:
        self._dirty = True

    def clear_dirty(self) -> None:
        self._dirty = False

    @property
    def is_dirty(self) -> bool:
        return self._dirty


class UserInfoState(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool = True


class UserState(BaseModel):
    users: Dict[int, UserInfoState] = Field(default_factory=dict)
    _dirty: bool = PrivateAttr(default=False)

    def mark_dirty(self) -> None:
        self._dirty = True

    def clear_dirty(self) -> None:
        self._dirty = False

    @property
    def is_dirty(self) -> bool:
        return self._dirty


class ServerRuntimeInfo(BaseModel):
    running: bool = False
    pid: Optional[int] = None
    players_online: int = 0
    online_players_list: List[str] = Field(default_factory=list)
    cpu_percent: float = 0.0
    memory_mb: float = 0.0


class RuntimeState(BaseModel):
    servers: Dict[str, ServerRuntimeInfo] = Field(default_factory=dict)
    active_tasks: Dict[str, Any] = Field(default_factory=dict)
    websocket_connections: int = 0
