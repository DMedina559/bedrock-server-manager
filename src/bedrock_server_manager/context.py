# src/bedrock_server_manager/context.py
"""
Defines the central application context.
"""

from __future__ import annotations

from logging import Logger
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from asyncio import AbstractEventLoop

    from .config.settings import Settings
    from .core.bedrock_process_manager import BedrockProcessManager
    from .core.bedrock_server import BedrockServer
    from .db.database import Database
    from .plugins.api_bridge import AppAPI
    from .plugins.plugin_manager import PluginManager
    from .web.resource_monitor import ResourceMonitor
    from .web.tasks import TaskManager
    from .web.websocket_manager import ConnectionManager


class AppContext:
    """
    A context object that holds application-wide instances and caches.
    """

    def __init__(
        self,
        config_dir: Optional[str] = None,
        data_dir: Optional[str] = None,
        db_url: Optional[str] = None,
        log_level: Optional[str] = None,
        logger: Optional[Logger] = None,
    ):
        """
        Initializes the AppContext.
        """

        self._config_dir: Optional[str] = config_dir
        self._data_dir: Optional[str] = data_dir
        self._db_url: Optional[str] = db_url
        self._log_level: Optional[str] = log_level
        self._logger: Optional[Logger] = logger
        self._settings: Optional["Settings"] = None
        self._db: Optional["Database"] = None
        self._bedrock_process_manager: Optional["BedrockProcessManager"] = None
        self._plugin_manager: Optional["PluginManager"] = None
        self._task_manager: Optional["TaskManager"] = None
        self._connection_manager: Optional["ConnectionManager"] = None
        self._resource_monitor: Optional["ResourceMonitor"] = None
        self._servers: Dict[str, "BedrockServer"] = {}
        self.loop: Optional["AbstractEventLoop"] = None
        self._api: Optional["AppAPI"] = None
        self._web_server: Optional[Any] = None
        self.splash_txt: Optional[str] = None
        self._log_dir: Optional[str] = None
        self._needs_setup: Optional[bool] = None
        self._pre_app_config_cache: Optional[Dict[str, Any]] = None

    def load(self):
        """
        Loads the application context by initializing the settings.
        """
        from .config.settings import Settings

        self.db.initialize()

        self._settings = Settings(
            db=self.db, config_dir=self.config_dir, data_dir=self.data_dir
        )
        self._settings.load()

        from .utils import get_utils

        self.splash_txt = get_utils._get_splash_text()

    def reload(self):
        """
        Reloads the application context by reloading settings and all components.
        """
        self.settings.reload()
        self.plugin_manager.reload()
        # self._servers.clear()

    @property
    def pre_app_config(self) -> Dict[str, Any]:
        """
        Lazily loads and caches the pre-application configuration dictionary
        from bedrock_server_manager.json (resolving CLI and Env overrides).
        """
        if self._pre_app_config_cache is None:
            from .config import bcm_config

            self._pre_app_config_cache = bcm_config.load_config()
        return self._pre_app_config_cache

    def get_pre_app_config(self, key: str, default: Any = None) -> Any:
        """
        Retrieves a single value from the cached pre-application configuration.
        Supports dot notation for nested keys (e.g., 'web.cors_origins').

        Args:
            key (str): The key of the value to retrieve.
            default (Any, optional): The default value to return if the key is not found.

        Returns:
            Any: The configuration value or the default.
        """
        keys = key.split(".")
        value = self.pre_app_config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

    @property
    def config_dir(self) -> str:
        """str: The absolute path to the application's configuration directory."""
        if self._config_dir is None:
            from .config import bcm_config

            self._config_dir = bcm_config.get_config_dir()
        return self._config_dir

    @property
    def data_dir(self) -> str:
        """str: The absolute path to the application's data directory."""
        if self._data_dir is None:
            self._data_dir = str(self.pre_app_config["data_dir"])
        return self._data_dir

    @property
    def db_url(self) -> str:
        """str: The application's configured database URL."""
        if self._db_url is None:
            self._db_url = str(self.pre_app_config.get("db_url"))
        return self._db_url

    @property
    def log_level(self) -> str:
        """str: The application's configured log level."""
        if self._log_level is None:
            self._log_level = str(self.pre_app_config.get("logging_level", "INFO"))
        return self._log_level

    @property
    def log_dir(self) -> str:
        """str: The absolute path to the application's logs directory."""
        if self._log_dir is None:
            import os

            self._log_dir = os.path.join(self.config_dir, "logs")
        return self._log_dir

    @property
    def needs_setup(self) -> bool:
        """
        bool: Indicates whether the application requires initial setup.

        Evaluates to True if no user with the role 'admin' exists in the database.
        The result is cached internally after the first check that returns False.
        """
        if self._needs_setup is False:
            return False

        if not self._db:
            return True

        from sqlalchemy.orm import Session

        from .db.models import User

        try:
            with Session(self.db.engine) as session:
                admin_user = session.query(User).filter(User.role == "admin").first()
                if admin_user:
                    self._needs_setup = False
                    return False
        except Exception:
            return True

        return True

    @property
    def api(self) -> "AppAPI":
        """
        Lazily loads and returns the API instance.
        """
        if not hasattr(self, "_api") or self._api is None:
            from .plugins.api_bridge import AppAPI

            self._api = AppAPI("CoreAPI", self, is_core=True)
        return self._api

    @property
    def db(self) -> "Database":
        """
        Lazily loads and returns the Database instance.
        """
        if self._db is None:
            from .db.database import Database

            self._db = Database(self.db_url)
        return self._db

    @property
    def settings(self) -> "Settings":
        """
        Returns the Settings instance.
        """
        if self._settings is None:
            raise RuntimeError(
                "Settings have not been loaded. Please call AppContext.load() first."
            )
        return self._settings

    @property
    def plugin_manager(self) -> "PluginManager":
        """
        Lazily loads and returns the PluginManager instance.
        """
        if self._plugin_manager is None:
            from .plugins.plugin_manager import PluginManager

            self._plugin_manager = PluginManager(self)
        return self._plugin_manager

    @property
    def task_manager(self) -> "TaskManager":
        """
        Lazily loads and returns the TaskManager instance.
        """
        if self._task_manager is None:
            from .web.tasks import TaskManager

            self._task_manager = TaskManager(app_context=self)
        return self._task_manager

    @property
    def connection_manager(self) -> "ConnectionManager":
        """
        Lazily loads and returns the ConnectionManager instance.
        """
        if self._connection_manager is None:
            from .web.websocket_manager import ConnectionManager

            self._connection_manager = ConnectionManager()
        return self._connection_manager

    @property
    def resource_monitor(self) -> "ResourceMonitor":
        """
        Lazily loads and returns the ResourceMonitor instance.
        """
        if self._resource_monitor is None:
            from .web.resource_monitor import ResourceMonitor

            self._resource_monitor = ResourceMonitor(app_context=self)
        return self._resource_monitor

    @property
    def bedrock_process_manager(self) -> "BedrockProcessManager":
        """
        Lazily loads and returns the BedrockProcessManager instance.
        """
        if self._bedrock_process_manager is None:
            from .core.bedrock_process_manager import BedrockProcessManager

            self._bedrock_process_manager = BedrockProcessManager(app_context=self)
        return self._bedrock_process_manager

    def get_server(self, server_name: str) -> "BedrockServer":
        """
        Retrieve or create a BedrockServer instance.
        """
        from .core.bedrock_server import BedrockServer

        if server_name not in self._servers:
            self._servers[server_name] = BedrockServer(server_name, app_context=self)
        return self._servers[server_name]

    def remove_server(self, server_name: str):
        """
        Stops a server, removes it from the process manager, and discards it from the context cache.
        """
        # 1. Get the server instance from the cache.
        if server_name in self._servers:
            server = self._servers[server_name]

            # 2. Stop the server if it is running.
            if server.is_running():
                server.stop()

            # 3. Remove from the AppContext cache.
            del self._servers[server_name]

    def stop_all_servers(self):
        """Stops all running servers sequentially in the application context cache."""
        import logging

        logger = logging.getLogger(__name__)
        logger.info("Context: Stopping all cached servers sequentially...")

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

    async def stop_all_servers_async(self):
        """Asynchronously stops all running servers concurrently."""
        import asyncio
        import logging

        logger = logging.getLogger(__name__)
        logger.info("Context: Stopping all cached servers concurrently...")

        async def _stop_server(server_name, server):
            if not server.is_running():
                return

            # Run the blocking stop operations in a separate thread
            # so we don't block the async event loop for Uvicorn
            def _do_stop():
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

            await asyncio.to_thread(_do_stop)
            logger.info(f"Context: Stopped server '{server_name}'")

        tasks = []
        for server_name, server in self._servers.items():
            tasks.append(_stop_server(server_name, server))

        if tasks:
            await asyncio.gather(*tasks)
