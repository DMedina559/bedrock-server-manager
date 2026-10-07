# src/bedrock_server_manager/state/app_state.py
"""
Central AppState class holding in-memory domain states.
"""

import asyncio
from dataclasses import dataclass, field
from typing import Optional

from .models import PluginState, RuntimeState, ServerState, UserState
from .settings import SettingsState


@dataclass
class AppState:
    settings: SettingsState = field(default_factory=SettingsState)
    servers: ServerState = field(default_factory=ServerState)
    plugins: PluginState = field(default_factory=PluginState)
    users: UserState = field(default_factory=UserState)
    runtime: RuntimeState = field(default_factory=RuntimeState)
    _lock: Optional[asyncio.Lock] = field(default=None, init=False, repr=False)

    @property
    def lock(self) -> asyncio.Lock:
        """Returns or initializes an asyncio.Lock for atomic state mutations across tasks."""
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    def is_dirty(self) -> bool:
        """Returns True if any persistent sub-state has pending modifications."""
        return (
            self.settings.is_dirty
            or self.servers.is_dirty
            or self.plugins.is_dirty
            or self.users.is_dirty
        )

    def clear_dirty(self) -> None:
        """Clears dirty tracking flags across all persistent sub-states."""
        self.settings.clear_dirty()
        self.servers.clear_dirty()
        self.plugins.clear_dirty()
        self.users.clear_dirty()
