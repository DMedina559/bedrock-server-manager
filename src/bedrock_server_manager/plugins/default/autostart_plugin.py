# autostart_servers.py
import asyncio
from typing import Any

from bedrock_server_manager import PluginBase, app_event


class AutostartServers(PluginBase):
    """
    Starts all servers with the autostart setting set to true on manager startup.
    """

    version = "1.1.0"
    description = (
        "Starts all servers with the autostart setting set to true on manager startup."
    )
    author = "dmedina559"
    name = "Auto Start Servers"

    @app_event("on_load")
    def plugin_loaded(self):
        """
        This event is called when the plugin is loaded by the manager.
        """
        self.logger.info(
            "Autostart Servers plugin loaded, checking for servers to start."
        )

    @app_event("on_manager_startup")
    async def autostart_servers(self, **kwargs: Any):

        # Run API calls in thread to not block startup loop
        result = await asyncio.to_thread(self.api.get_all_servers_data)
        servers = result.get("servers", [])

        for server in servers:
            server_name = server.get("name")
            if not server_name:
                continue

            setting_result = await asyncio.to_thread(
                self.api.get_server_setting, server_name, "settings.autostart"
            )
            server_settings = setting_result.get("value")

            if server_settings:
                self.logger.info(
                    f"Server '{server_name}' has autostart enabled, starting it now (background task)."
                )
                # Use the task manager to start the server in the background so app startup isn't blocked
                # especially if an update is required.
                self.api.app_context.task_manager.run_task(
                    self.api.start_server,
                    server_name=server_name,
                    username="System (Autostart)",
                )
