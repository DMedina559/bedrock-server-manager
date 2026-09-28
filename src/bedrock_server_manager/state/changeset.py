# src/bedrock_server_manager/state/changeset.py
"""
Structured ChangeSet representation for capturing state mutations across domain boundaries.
"""

from typing import Set

from pydantic import BaseModel, Field


class ChangeSet(BaseModel):
    """
    Captures modified entity keys across application domains.
    Used by Storage and Service boundaries to persist and broadcast targeted mutations.
    """

    settings_changed: Set[str] = Field(default_factory=set)
    servers_changed: Set[str] = Field(default_factory=set)
    plugins_changed: Set[str] = Field(default_factory=set)
    users_changed: Set[str] = Field(default_factory=set)

    def is_empty(self) -> bool:
        """Returns True if no entity changes are recorded."""
        return not (
            self.settings_changed
            or self.servers_changed
            or self.plugins_changed
            or self.users_changed
        )

    def add_setting(self, key: str) -> None:
        """Adds a modified setting key."""
        self.settings_changed.add(key)

    def add_server(self, server_name: str) -> None:
        """Adds a modified server name."""
        self.servers_changed.add(server_name)

    def add_plugin(self, plugin_name: str) -> None:
        """Adds a modified plugin name."""
        self.plugins_changed.add(plugin_name)

    def add_user(self, username: str) -> None:
        """Adds a modified username."""
        self.users_changed.add(username)

    def merge(self, other: "ChangeSet") -> None:
        """Merges another ChangeSet into this instance."""
        self.settings_changed.update(other.settings_changed)
        self.servers_changed.update(other.servers_changed)
        self.plugins_changed.update(other.plugins_changed)
        self.users_changed.update(other.users_changed)
