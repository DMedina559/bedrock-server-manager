from __future__ import annotations

from typing import TYPE_CHECKING, Dict

if TYPE_CHECKING:
    from .config.settings import Settings
    from .core.bedrock_server import BedrockServer
    from .core.manager import BedrockServerManager
    from .plugins.plugin_manager import PluginManager
    from .core.bedrock_process_manager import BedrockProcessManager


class AppContext:
    """
    A context object that holds application-wide instances and caches.
    """

    def __init__(
        self,
        settings: "Settings" | None = None,
        manager: "BedrockServerManager" | None = None,
    ):
        """
        Initializes the AppContext.
        """
        self.settings: "Settings" | None = settings
        self.manager: "BedrockServerManager" | None = manager
        self._bedrock_process_manager: "BedrockProcessManager" | None = None
        self._plugin_manager: "PluginManager" | None = None
        self._servers: Dict[str, "BedrockServer"] = {}

    def load(self):
        """
        Loads the application context by initializing the settings and manager.
        """
        from .config.settings import Settings
        from .core.manager import BedrockServerManager

        if self.settings is None:
            self.settings = Settings()
            self.settings.load()

        if self.manager is None:
            assert self.settings is not None
            self.manager = BedrockServerManager(self.settings)
            self.manager.load()

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

    @property
    def bedrock_process_manager(self) -> "BedrockProcessManager":
        """
        Lazily loads and returns the BedrockProcessManager instance.
        """
        if self._bedrock_process_manager is None:
            from .core.bedrock_process_manager import BedrockProcessManager

            self._bedrock_process_manager = BedrockProcessManager(app_context=self)
        return self._bedrock_process_manager

    @bedrock_process_manager.setter
    def bedrock_process_manager(self, value: "BedrockProcessManager"):
        """
        Sets the BedrockProcessManager instance.
        """
        self._bedrock_process_manager = value

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
