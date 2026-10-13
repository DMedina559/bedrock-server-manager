"""Typed access to a server's persisted configuration."""

from typing import TYPE_CHECKING, cast

from pydantic import JsonValue

from ...error import APICancelledError, ConfigurationError, MissingArgumentError
from ...events.bus import correlation_scope
from ...events.control import CancellableEvent
from ...events.publisher import EventPublisher
from ...events.server import StatusRequest, StatusResult
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

    async def set_status(
        self, status: str, events: EventPublisher | None = None
    ) -> StatusResult:
        request = StatusRequest(server_name=self.server.server_name, status=status)
        data = {**request.model_dump(), "request": request}
        control = CancellableEvent()
        with correlation_scope():
            if events is not None and events.accepting:
                try:
                    await events.emit(
                        "before_server_status_change", {**data, "event": control}
                    )
                finally:
                    control.seal()
                if control.is_cancelled:
                    raise APICancelledError(
                        control.cancel_reason or "Status change cancelled"
                    )
            previous = self.snapshot().status
            await self.update("server_info.status", request.status)
            result = StatusResult(
                message=f"Server status set to {request.status}.",
                server_name=request.server_name,
                previous_status=previous,
                new_status=request.status,
            )
            if events is not None and events.accepting:
                await events.emit(
                    "after_server_status_change", {**data, "result": result}
                )
            return result

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
