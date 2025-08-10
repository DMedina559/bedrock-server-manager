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
    ):
        """
        Initializes the AppContext.

        Args:
            settings (Settings): The application settings instance.
            manager (BedrockServerManager): The BedrockServerManager instance.
        """
        from .core.bedrock_process_manager import BedrockProcessManager

        self.settings = settings
        self.manager = manager
        self._plugin_manager: "PluginManager" | None = None
        self.bedrock_process_manager = BedrockProcessManager(app_context=self)
        self._servers: Dict[str, "BedrockServer"] = {}

    @property
    def plugin_manager(self) -> "PluginManager":
        """
        Lazily loads and returns the PluginManager instance.
        """
        if self._plugin_manager is None:
            from .plugins.plugin_manager import PluginManager

            self._plugin_manager = PluginManager(self.settings)
            self._plugin_manager.set_app_context(self)
        return self._plugin_manager

    @plugin_manager.setter
    def plugin_manager(self, value: "PluginManager"):
        """
        Sets the PluginManager instance.
        """
        self._plugin_manager = value

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
            self._servers[server_name] = BedrockServer(server_name, app_context=self)
        return self._servers[server_name]
