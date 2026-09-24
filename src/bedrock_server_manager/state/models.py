# src/bedrock_server_manager/state/models.py
"""
Typed domain state models for ServerState, PluginState, UserState, and RuntimeState.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, PrivateAttr


class ServerConfigState(BaseModel):
    name: str
    server_path: str
    version: Optional[str] = None
    autostart: bool = False
    port: int = 19132
    v4_port: int = 19132
    v6_port: int = 19133
    settings: Dict[str, Any] = Field(default_factory=dict)


class ServerState(BaseModel):
    servers: Dict[str, ServerConfigState] = Field(default_factory=dict)
    _dirty: bool = PrivateAttr(default=False)

    def mark_dirty(self) -> None:
        self._dirty = True

    def clear_dirty(self) -> None:
        self._dirty = False

    @property
    def is_dirty(self) -> bool:
        return self._dirty


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
