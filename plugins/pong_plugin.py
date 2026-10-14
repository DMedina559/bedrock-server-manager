"""Listen for the ping example's typed event."""

from bedrock_server_manager import PluginBase, app_event


class PongPlugin(PluginBase):
    version = "2.0.0"
    name = "Pong Example"
    description = "Log server pings from the ping example."
    dependencies = ["ping_plugin"]

    @app_event("ping_plugin:ping")
    async def received(self, server_name: str, **kwargs):
        self.logger.info(
            "Received ping for %s from %s",
            server_name,
            kwargs.get("_triggering_plugin", "unknown"),
        )
