# autostart_servers.py
from typing import Any

from bedrock_server_manager import PluginBase, app_event
from bedrock_server_manager.models import (
    GetAllServersDataRequest,
    GetServerSettingRequest,
    StartServerRequest,
)


class AutostartServers(PluginBase):
    """Start all servers with the autostart setting set to true on manager startup."""

    version = "1.2.0"
    permissions = ["servers:lifecycle", "servers:read"]
    description = (
        "Starts all servers with the autostart setting set to true on manager startup."
    )
    author = "dmedina559"
    name = "Auto Start Servers"

    @app_event("on_load")
    async def plugin_loaded(self):
        """
        This event is called when the plugin is loaded by the manager.
        """
        self.logger.debug(
            "Autostart Servers plugin loaded, checking for servers to start."
        )

    @app_event("on_manager_startup")
    async def autostart_servers(self, **kwargs: Any):

        # Read server data asynchronously during startup.
        result = await self.api.application.get_all_servers_data(
            request=GetAllServersDataRequest()
        )
        servers = result.servers

        for server in servers:
            server_name = server.name
            if not server_name:
                continue

            setting_result = await self.api.server.get_setting(
                request=GetServerSettingRequest(
                    server_name=server_name, key="settings.autostart"
                )
            )
            server_settings = setting_result.value

            if server_settings:
                self.logger.info(
                    "Server '%s' has autostart enabled, starting it now (background task).",
                    server_name,
                )
                # Use the task manager to start the server in the background so app startup isn't blocked
                # especially if an update is required.
                await self.api.runtime.run_task(
                    self.api.server.start,
                    request=StartServerRequest(server_name=server_name),
                    username="System (Autostart)",
                )
