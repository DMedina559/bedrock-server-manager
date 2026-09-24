# src/bedrock_server_manager/state/app_state.py
"""
Central AppState class holding in-memory domain states.
"""

from pydantic import BaseModel, Field

from .models import PluginState, RuntimeState, ServerState, UserState
from .settings import SettingsState


class AppState(BaseModel):
    settings: SettingsState = Field(default_factory=SettingsState)
    servers: ServerState = Field(default_factory=ServerState)
    plugins: PluginState = Field(default_factory=PluginState)
    users: UserState = Field(default_factory=UserState)
    runtime: RuntimeState = Field(default_factory=RuntimeState)

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
