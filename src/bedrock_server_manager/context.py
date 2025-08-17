from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional

if TYPE_CHECKING:
    from .config.settings import Settings
    from .core.bedrock_server import BedrockServer
    from .core.manager import BedrockServerManager
    from .plugins.plugin_manager import PluginManager
    from .core.bedrock_process_manager import BedrockProcessManager
    from .db.database import Database


class AppContext:
    """
    A context object that holds application-wide instances and caches.
    """

    def __init__(
        self,
        settings: Optional["Settings"] = None,
        manager: Optional["BedrockServerManager"] = None,
        db: Optional["Database"] = None,
    ):
        """
        Initializes the AppContext.
        """
        self.settings: Optional["Settings"] = settings
        self.manager: Optional["BedrockServerManager"] = manager
        self._bedrock_process_manager: Optional["BedrockProcessManager"] = None
        self._plugin_manager: Optional["PluginManager"] = None
        self._db: Optional["Database"] = db
        self._servers: Dict[str, "BedrockServer"] = {}

    def load(self):
        """
        Loads the application context by initializing the settings and manager.
        """
        from .config.settings import Settings
        from .core.manager import BedrockServerManager

        self.db.initialize()

        if self.settings is None:
            self.settings = Settings()
            self.settings.load()

        if self.manager is None:
            assert self.settings is not None
            self.manager = BedrockServerManager(self.settings)
            self.manager.load()

    @property
    def db(self) -> "Database":
        """
        Lazily loads and returns the Database instance.
        """
        if self._db is None:
            from .db.instances import get_db_instance

            self._db = get_db_instance()
        return self._db

    @db.setter
    def db(self, value: "Database"):
        """
        Sets the Database instance.
        """
        from .db.instances import set_db_instance

        self._db = value
        set_db_instance(self._db)

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
        Retrieve or create a BedrockServer instance.
        Args:
            server_name: The name of the server to get.
        Returns: The BedrockServer instance.
        """
        from .core.bedrock_server import BedrockServer

        if server_name not in self._servers:
            self._servers[server_name] = BedrockServer(
                server_name, settings_instance=self.settings
            )
        return self._servers[server_name]
