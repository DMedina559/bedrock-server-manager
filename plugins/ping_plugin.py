"""Publish an owned, typed event after a successful server start."""

from pydantic import BaseModel, ConfigDict

from bedrock_server_manager import PluginBase, app_event
from bedrock_server_manager.api.models import StartServerResponse


class PingPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    server_name: str


class PingPlugin(PluginBase):
    version = "2.0.0"
    name = "Ping Example"
    description = "Publish a typed ping after server startup."

    @app_event("on_load")
    async def loaded(self, **kwargs):
        self.api.events.define("ping_plugin:ping", PingPayload)

    @app_event("after_server_start")
    async def send_ping_event(
        self, server_name: str, result: StartServerResponse, **kwargs
    ):
        if result.status == "success":
            await self.api.events.emit("ping_plugin:ping", server_name=server_name)
