# src/bedrock_server_manager/context.py
"""
Defines the central application context.

This module provides the :class:`~.AppContext` class, which serves as a singleton-like
container for application-wide objects and services, such as settings, database,
plugin manager, and server instances. It ensures circular dependencies are managed
via lazy loading and property accessors.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from asyncio import AbstractEventLoop

    from .config.settings import Settings
    from .core.bedrock_process_manager import BedrockProcessManager
    from .core.bedrock_server import BedrockServer
    from .db.database import Database
    from .plugins.api_bridge import CoreAPI
    from .plugins.plugin_manager import PluginManager
    from .web.resource_monitor import ResourceMonitor
    from .web.tasks import TaskManager
    from .web.websocket_manager import ConnectionManager


class AppContext:
    """
    A context object that holds application-wide instances and caches.

    The ``AppContext`` acts as a central hub for accessing core application components.
    It manages the lifecycle of singletons like the :class:`~.plugins.plugin_manager.PluginManager`,
    settings, and database connection.
    Most properties are lazily initialized to improve startup time and handle
    dependency resolution order.

    Attributes:
        _settings (Optional[Settings]): Internal storage for the settings instance.
        _db (Optional[Database]): Internal storage for the database handler.
        _servers (Dict[str, BedrockServer]): Cache of instantiated server objects.
        _web_server (Optional[Any]): The running Uvicorn server instance, if available.
        loop (Optional[AbstractEventLoop]): The asyncio event loop, if set.
    """

    def __init__(
        self,
        settings: Optional["Settings"] = None,
        db: Optional["Database"] = None,
    ):
        """
        Initializes the AppContext.

        Args:
            settings (Optional[Settings]): Pre-existing settings instance.
            db (Optional[Database]): Pre-existing database instance.
        """
        from .utils import get_utils

        self._settings: Optional["Settings"] = settings
        self._db: Optional["Database"] = db
        self._bedrock_process_manager: Optional["BedrockProcessManager"] = None
        self._plugin_manager: Optional["PluginManager"] = None
        self._task_manager: Optional["TaskManager"] = None
        self._connection_manager: Optional["ConnectionManager"] = None
        self._resource_monitor: Optional["ResourceMonitor"] = None
        self._servers: Dict[str, "BedrockServer"] = {}
        self.loop: Optional["AbstractEventLoop"] = None
        self._api: Optional["CoreAPI"] = None
        self._web_server: Optional[Any] = None
        self.splash_txt: Optional[str] = str(get_utils._get_splash_text())

    def load(self):
        """
        Loads the application context by initializing the settings.

        This method should be called early in the application startup phase to
        ensure core components like the database and settings are ready.
        """
        from .config.settings import Settings

        self.db.initialize()

        if self._settings is None:
            self._settings = Settings(db=self.db)
            self._settings.load()

    def reload(self):
        """
        Reloads the application context by reloading settings and all components.

        This triggers a reload on the settings and plugin manager,
        allowing configuration changes to take effect without restarting the
        entire process.
        """
        self.settings.reload()
        self.plugin_manager.reload()
        # self._servers.clear()

    @property
    def api(self) -> "CoreAPI":
        """
        Lazily loads and returns the CoreAPI instance.

        Returns:
            CoreAPI: The internal core API bridge.
        """
        if not hasattr(self, "_api") or self._api is None:
            from .plugins.api_bridge import CoreAPI

            self._api = CoreAPI(self)
        return self._api

    @property
    def settings(self) -> "Settings":
        """
        Returns the Settings instance.

        Returns:
            Settings: The global settings object.

        Raises:
            RuntimeError: If the settings have not been loaded yet.
        """
        if self._settings is None:
            raise RuntimeError(
                "Settings have not been loaded. Please call AppContext.load() first."
            )
        return self._settings

    @property
    def db(self) -> "Database":
        """
        Lazily loads and returns the Database instance.

        Returns:
            Database: The database handler.
        """
        if self._db is None:
            from .db.database import Database

            self._db = Database()
        return self._db

    @property
    def plugin_manager(self) -> "PluginManager":
        """
        Lazily loads and returns the PluginManager instance.

        Returns:
            PluginManager: The plugin manager.
        """
        if self._plugin_manager is None:
            from .plugins.plugin_manager import PluginManager

            self._plugin_manager = PluginManager(self.settings)
            self._plugin_manager.set_app_context(self)
        return self._plugin_manager

    @property
    def task_manager(self) -> "TaskManager":
        """
        Lazily loads and returns the TaskManager instance.

        Returns:
            TaskManager: The task manager for background operations.
        """
        if self._task_manager is None:
            from .web.tasks import TaskManager

            self._task_manager = TaskManager(app_context=self)
        return self._task_manager

    @property
    def connection_manager(self) -> "ConnectionManager":
        """
        Lazily loads and returns the ConnectionManager instance.

        Returns:
            ConnectionManager: The WebSocket connection manager.
        """
        if self._connection_manager is None:
            from .web.websocket_manager import ConnectionManager

            self._connection_manager = ConnectionManager()
        return self._connection_manager

    @property
    def resource_monitor(self) -> "ResourceMonitor":
        """
        Lazily loads and returns the ResourceMonitor instance.

        Returns:
            ResourceMonitor: The system resource monitor.
        """
        if self._resource_monitor is None:
            from .web.resource_monitor import ResourceMonitor

            self._resource_monitor = ResourceMonitor(app_context=self)
        return self._resource_monitor

    @property
    def bedrock_process_manager(self) -> "BedrockProcessManager":
        """
        Lazily loads and returns the BedrockProcessManager instance.

        Returns:
            BedrockProcessManager: The server process monitor.
        """
        if self._bedrock_process_manager is None:
            from .core.bedrock_process_manager import BedrockProcessManager

            self._bedrock_process_manager = BedrockProcessManager(app_context=self)
        return self._bedrock_process_manager

    def get_server(self, server_name: str) -> "BedrockServer":
        """
        Retrieve or create a BedrockServer instance.

        Args:
            server_name (str): The name of the server to get.

        Returns:
            BedrockServer: The requested BedrockServer instance.
        """
        from .core.bedrock_server import BedrockServer

        if server_name not in self._servers:
            self._servers[server_name] = BedrockServer(
                server_name, settings_instance=self.settings, app_context=self
            )
        return self._servers[server_name]

    def remove_server(self, server_name: str):
        """
        Stops a server, removes it from the process manager, and discards it from the context cache.

        Args:
            server_name (str): The name of the server to remove.
        """
        # 1. Get the server instance from the cache.
        if server_name in self._servers:
            server = self._servers[server_name]

            # 2. Stop the server if it is running.
            # The BedrockServer.stop() method should handle setting the
            # intentionally_stopped flag, which will cause the process manager
            # to automatically un-monitor it.
            if server.is_running():
                server.stop()

            # 3. Remove from the AppContext cache.
            del self._servers[server_name]

    def stop_all_servers(self):
        """Stops all running servers in the application context cache using the API bridge."""
        import logging

        logger = logging.getLogger(__name__)
        logger.info("Context: Stopping all cached servers...")

        for server_name, server in self._servers.items():
            if server.is_running():
                if hasattr(self, "api"):
                    try:
                        self.api.stop_server(server_name)
                    except Exception as e:
                        logger.error(
                            f"Context: Error stopping '{server_name}' via API: {e}. Attempting direct stop."
                        )
                        server.stop()
                else:
                    server.stop()
                logger.info(f"Context: Stopped server '{server_name}'")
