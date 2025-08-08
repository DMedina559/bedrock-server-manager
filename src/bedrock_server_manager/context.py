from __future__ import annotations

from typing import TYPE_CHECKING, Dict

if TYPE_CHECKING:
    from .config.settings import Settings
    from .core.bedrock_server import BedrockServer
    from .core.manager import BedrockServerManager
    from .plugins.plugin_manager import PluginManager


class AppContext:
    """
    A context object that holds application-wide instances and caches.
    """

    def __init__(
        self,
        settings: "Settings",
        manager: "BedrockServerManager",
        plugin_manager: "PluginManager",
    ):
        """
        Initializes the AppContext.

        Args:
            settings (Settings): The application settings instance.
            manager (BedrockServerManager): The BedrockServerManager instance.
            plugin_manager (PluginManager): The PluginManager instance.
        """
        self.settings = settings
        self.manager = manager
        self.plugin_manager = plugin_manager
        self._servers: Dict[str, "BedrockServer"] = {}

    def get_server(self, server_name: str) -> "BedrockServer":
        """
        Retrieves or creates a BedrockServer instance.

        Args:
            server_name (str): The name of the server.

        Returns:
            BedrockServer: The BedrockServer instance.
        """
        from .core.bedrock_server import BedrockServer

        if server_name not in self._servers:
            self._servers[server_name] = BedrockServer(
                server_name, settings_instance=self.settings
            )
        return self._servers[server_name]
