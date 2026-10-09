"""Typed access to a server's persisted configuration."""

from typing import TYPE_CHECKING, cast

from pydantic import JsonValue

from ...error import ConfigurationError, MissingArgumentError
from ...services.server_service import ServerService
from ...state.models import ServerConfigState

if TYPE_CHECKING:
    from ..bedrock_server import BedrockServer


class ServerConfiguration:
    """Read snapshots without writes; persist mutations through ServerService."""

    def __init__(self, server: "BedrockServer") -> None:
        self.server = server

    def snapshot(self) -> ServerConfigState:
        state = self.server.state
        if state is None:
            raise ConfigurationError("Server configuration requires AppState.")
        return state.servers.get(self.server.server_name) or ServerConfigState(
            server_name=self.server.server_name
        )

    async def update(self, key: str, value: JsonValue) -> None:
        if not key:
            raise MissingArgumentError("Config key cannot be empty.")
        if self.server.state is None or self.server.storage is None:
            raise ConfigurationError(
                "Server configuration writes require AppState and Storage."
            )
        await ServerService(self.server.state, self.server.storage).update_setting(
            self.server.server_name, key, value
        )

    def read(self, key: str) -> JsonValue:
        if not key:
            raise MissingArgumentError("Config key cannot be empty.")
        parts = key.split(".")
        record = self.snapshot()
        fields = {
            "server_info": {"installed_version", "status"},
            "settings": {"autoupdate", "autostart", "target_version"},
        }
        if len(parts) == 1 and parts[0] in fields:
            return {
                name: cast(JsonValue, getattr(record, name))
                for name in fields[parts[0]]
            }
        if len(parts) == 2 and parts[1] in fields.get(parts[0], set()):
            return cast(JsonValue, record.model_dump(mode="json")[parts[1]])
        if parts[0] == "custom":
            value: JsonValue = record.custom
            for part in parts[1:]:
                if not isinstance(value, dict):
                    return None
                value = value.get(part)
            return value
        return None

    def as_settings(self) -> dict[str, JsonValue]:
        """Adapt the typed snapshot to the existing public settings response."""
        record = self.snapshot()
        return {
            "server_info": {
                "installed_version": record.installed_version,
                "status": record.status,
            },
            "settings": {
                "autoupdate": record.autoupdate,
                "autostart": record.autostart,
                "target_version": record.target_version,
            },
            "custom": record.custom,
        }
