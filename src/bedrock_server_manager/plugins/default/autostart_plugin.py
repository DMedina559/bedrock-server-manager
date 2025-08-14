# autostart_servers.py
from bedrock_server_manager import PluginBase
from typing import Any


class AutostartServers(PluginBase):
    """
    Starts all servers with the autostart setting set to true on manager startup.
    """

    version = "1.0.0"

    def on_load(self):
        """
        This event is called when the plugin is loaded by the manager.
        """
        self.logger.info(
            "Autostart Servers plugin loaded, checking for servers to start."
        )

    def on_manager_startup(self, **kwargs: Any):
        result = self.api.get_all_servers_data()
        servers = result["servers"]
        for server in servers:
            server_name = server["name"]
            result = self.api.get_server_setting(server_name, "settings.autostart")
            server_settings = result["value"]

            if server_settings:
                self.logger.info(
                    f"Server '{server_name}' has autostart enabled, starting it now."
                )
                self.api.start_server(server_name)
