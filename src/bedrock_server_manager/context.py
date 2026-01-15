# src/bedrock_server_manager/context.py
"""
Defines the central application context.

This module provides the :class:`~.AppContext` class, which serves as a singleton-like
container for application-wide objects and services, such as settings, database,
plugin manager, and server instances. It ensures circular dependencies are managed
via lazy loading and property accessors.
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional

if TYPE_CHECKING:
    from asyncio import AbstractEventLoop

    from fastapi.templating import Jinja2Templates

    from .config.settings import Settings
    from .core.bedrock_process_manager import BedrockProcessManager
    from .core.bedrock_server import BedrockServer
    from .core.manager import BedrockServerManager
    from .db.database import Database
    from .plugins.plugin_manager import PluginManager
    from .web.resource_monitor import ResourceMonitor
    from .web.tasks import TaskManager
    from .web.websocket_manager import ConnectionManager


class AppContext:
    """
    A context object that holds application-wide instances and caches.

    The ``AppContext`` acts as a central hub for accessing core application components.
    It manages the lifecycle of singletons like the :class:`~.core.manager.BedrockServerManager`,
    :class:`~.plugins.plugin_manager.PluginManager`, and database connection.
    Most properties are lazily initialized to improve startup time and handle
    dependency resolution order.

    Attributes:
        _settings (Optional[Settings]): Internal storage for the settings instance.
        _manager (Optional[BedrockServerManager]): Internal storage for the main manager.
        _db (Optional[Database]): Internal storage for the database handler.
        _servers (Dict[str, BedrockServer]): Cache of instantiated server objects.
        loop (Optional[AbstractEventLoop]): The asyncio event loop, if set.
    """

    def __init__(
        self,
        settings: Optional["Settings"] = None,
        manager: Optional["BedrockServerManager"] = None,
        db: Optional["Database"] = None,
    ):
        """
        Initializes the AppContext.

        Args:
            settings (Optional[Settings]): Pre-existing settings instance.
            manager (Optional[BedrockServerManager]): Pre-existing manager instance.
            db (Optional[Database]): Pre-existing database instance.
        """
        self._settings: Optional["Settings"] = settings
        self._manager: Optional["BedrockServerManager"] = manager
        self._db: Optional["Database"] = db
        self._bedrock_process_manager: Optional["BedrockProcessManager"] = None
        self._plugin_manager: Optional["PluginManager"] = None
        self._task_manager: Optional["TaskManager"] = None
        self._connection_manager: Optional["ConnectionManager"] = None
        self._resource_monitor: Optional["ResourceMonitor"] = None
        self._servers: Dict[str, "BedrockServer"] = {}
        self._templates: Optional["Jinja2Templates"] = None
        self.loop: Optional["AbstractEventLoop"] = None

    def load(self):
        """
        Loads the application context by initializing the settings and manager.

        This method should be called early in the application startup phase to
        ensure core components like the database and settings are ready.
        """
        from .config.settings import Settings
        from .core.manager import BedrockServerManager

        self.db.initialize()

        if self._settings is None:
            self._settings = Settings(db=self.db)
            self._settings.load()

        if self._manager is None:
            assert self._settings is not None
            self._manager = BedrockServerManager(self._settings)
            self._manager.load()

    def reload(self):
        """
        Reloads the application context by reloading settings and all components.

        This triggers a reload on the settings, main manager, and plugin manager,
        allowing configuration changes to take effect without restarting the
        entire process.
        """
        self.settings.reload()
        self.manager.reload()
        self.plugin_manager.reload()
        # self._servers.clear()
        self._templates = None

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
    def manager(self) -> "BedrockServerManager":
        """
        Returns the BedrockServerManager instance.

        Returns:
            BedrockServerManager: The main application manager.

        Raises:
            RuntimeError: If the manager has not been loaded yet.
        """
        if self._manager is None:
            raise RuntimeError(
                "BedrockServerManager have not been loaded. Please call AppContext.load() first."
            )
        return self._manager

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

    @property
    def templates(self) -> "Jinja2Templates":
        """
        Lazily loads and returns the Jinja2Templates instance.

        This sets up the Jinja2 environment, including default filters, globals,
        and template search paths (including those from plugins).

        Returns:
            Jinja2Templates: The configured Jinja2 templates object.
        """
        if self._templates is None:
            from fastapi.templating import Jinja2Templates

            from .config import SCRIPT_DIR, app_name_title, get_installed_version
            from .utils import get_utils

            app_path = os.path.join(SCRIPT_DIR, "web", "app.py")
            APP_ROOT = os.path.dirname(os.path.abspath(app_path))
            TEMPLATES_DIR = os.path.join(APP_ROOT, "templates")

            all_template_dirs = [Path(TEMPLATES_DIR)]
            if self.plugin_manager.plugin_template_paths:
                unique_plugin_paths = {
                    p
                    for p in self.plugin_manager.plugin_template_paths
                    if isinstance(p, Path)
                }
                all_template_dirs.extend(list(unique_plugin_paths))

            self._templates = Jinja2Templates(directory=all_template_dirs)
            self._templates.env.filters["basename"] = os.path.basename
            self._templates.env.globals["app_name"] = app_name_title
            self._templates.env.globals["app_version"] = get_installed_version()
            self._templates.env.globals["splash_text"] = get_utils._get_splash_text()
            self._templates.env.globals["panorama_url"] = "/api/panorama"
            self._templates.env.globals["settings"] = self.settings

        return self._templates

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
                server_name, settings_instance=self.settings
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
