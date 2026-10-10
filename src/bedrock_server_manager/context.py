# src/bedrock_server_manager/context.py
"""
Defines the central application context.
"""

from __future__ import annotations

from logging import Logger, getLogger
from typing import TYPE_CHECKING, Any, Dict, Optional

from sqlalchemy import inspect, select

from .logging import log_operation_error

if TYPE_CHECKING:
    from asyncio import AbstractEventLoop

    from .config.settings import Settings
    from .core.bedrock_process_manager import BedrockProcessManager
    from .core.bedrock_server import BedrockServer
    from .db.database import Database
    from .db.storage import Storage
    from .plugins.api_bridge import AppAPI
    from .plugins.plugin_manager import PluginManager
    from .services.plugin_service import PluginService
    from .services.server_service import ServerService
    from .services.settings_service import SettingsService
    from .services.user_service import UserService
    from .state.app_state import AppState
    from .web.log_streamer import LogStreamer
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
        self._log_dir: Optional[str] = None
        self._db_url: Optional[str] = db_url
        self._log_level: Optional[str] = log_level
        self._logger: Optional[Logger] = logger
        self._settings: Optional["Settings"] = None
        self._db: Optional["Database"] = None
        self._state: Optional["AppState"] = None
        self._storage: Optional["Storage"] = None
        self._bedrock_process_manager: Optional["BedrockProcessManager"] = None
        self._plugin_manager: Optional["PluginManager"] = None
        self._task_manager: Optional["TaskManager"] = None
        self._connection_manager: Optional["ConnectionManager"] = None
        self._resource_monitor: Optional["ResourceMonitor"] = None
        self._log_streamer: Optional["LogStreamer"] = None
        self._api: Optional["AppAPI"] = None

        self.loop: Optional["AbstractEventLoop"] = None
        self._web_server: Optional[Any] = None

        self._servers: Dict[str, "BedrockServer"] = {}
        self.splash_txt: Optional[str] = None
        self._needs_setup: Optional[bool] = None

        self._pre_app_config_cache: Optional[Dict[str, Any]] = None
        self._settings_service: Optional["SettingsService"] = None
        self._server_service: Optional["ServerService"] = None
        self._plugin_service: Optional["PluginService"] = None
        self._user_service: Optional["UserService"] = None

    async def load(self):
        """
        Loads the application context by initializing the settings, AppState, and Storage.
        """
        from . import api  # noqa: F401
        from .config.settings import Settings
        from .db.storage import Storage
        from .state.app_state import AppState

        self.db.initialize()

        self._storage = Storage(db=self.db, data_dir=self.data_dir)
        self._state = AppState()
        self._settings_service = None
        self._server_service = None
        self._plugin_service = None
        self._user_service = None
        await self._storage.load_state(self._state)

        if self._settings is not None:
            self._settings.app_context = self
        else:
            self._settings = Settings(
                config_dir=self.config_dir,
                data_dir=self.data_dir,
                app_context=self,
            )
        await self._settings.load()

        from .utils import get_utils

        self.splash_txt = get_utils._get_splash_text()

    async def reload(self):
        """
        Reloads the application context by reloading settings and all components.
        """
        self._pre_app_config_cache = None
        self._needs_setup = None
        self._config_dir = None
        self._data_dir = None
        self._db_url = None
        self._log_level = None
        self._log_dir = None

        if self._storage and self._state:
            await self._storage.load_state(self._state)

        await self.settings.reload()

        if self._plugin_manager is not None:
            await self._plugin_manager.reload()

        if self._resource_monitor is not None:
            await self._resource_monitor.shutdown()
            self._resource_monitor.start()

        if self._log_streamer is not None:
            await self._log_streamer.shutdown()
            self._log_streamer.start()

    async def flush(self):
        """
        Flushes any unpersisted application state to storage.
        """
        if self._storage and self._state:
            await self._storage.flush(self._state)

    async def shutdown(self):
        """
        Shuts down application context components and flushes pending state to storage.
        """
        errors: list[Exception] = []
        if self._task_manager is not None:
            self._task_manager.begin_shutdown()
        for producer in (self._bedrock_process_manager, self._plugin_manager):
            if producer is not None:
                try:
                    await producer.quiesce()
                except Exception as error:
                    errors.append(error)
        components = (
            self._task_manager,
            self._plugin_manager,
            self._bedrock_process_manager,
            self._resource_monitor,
            self._log_streamer,
            self._connection_manager,
        )
        for component in components:
            if component is not None:
                try:
                    await component.shutdown()
                except Exception as error:
                    errors.append(error)
                    log_operation_error(
                        getLogger(__name__),
                        "Component shutdown failed: %s",
                        type(component).__name__,
                        error=error,
                    )
        try:
            await self.flush()
        except Exception as error:
            errors.append(error)
        finally:
            if self._db is not None:
                try:
                    await self._db.shutdown()
                except Exception as error:
                    errors.append(error)
        if errors:
            raise ExceptionGroup("Application shutdown failed", errors)

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

        from .db.models import User
        from .utils.general import run_async

        async def _check():
            if not self.db.engine:
                self.db.initialize()
            assert self.db.engine is not None
            async with self.db.engine.connect() as conn:

                def _sync_inspect_and_query(sync_conn):
                    inspector = inspect(sync_conn)
                    if not inspector.has_table("users"):
                        return True
                    res = sync_conn.execute(
                        select(User).filter(
                            User.role == "admin", User.is_active.is_(True)
                        )
                    )
                    return res.scalars().first() is None

                return await conn.run_sync(_sync_inspect_and_query)

        try:
            needs = bool(run_async(_check()))
            if not needs:
                self._needs_setup = False
            return needs
        except Exception:
            return True

    @property
    def api(self) -> "AppAPI":
        """
        Lazily loads and returns the API instance.
        """
        if not hasattr(self, "_api") or self._api is None:
            from .plugins.api_bridge import create_app_api

            self._api = create_app_api("CoreAPI", self, is_core=True)
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
    def state(self) -> "AppState":
        """
        Returns the AppState instance.
        """
        if self._state is None:
            from .error import BSMError

            raise BSMError(
                "AppContext.state accessed before AppContext.load() was called."
            )
        return self._state

    @property
    def storage(self) -> "Storage":
        """
        Returns the Storage instance.
        """
        if self._storage is None:
            from .error import BSMError

            raise BSMError(
                "AppContext.storage accessed before AppContext.load() was called."
            )
        return self._storage

    @property
    def settings(self) -> "Settings":
        """
        Returns the Settings instance.
        """
        if self._settings is None:
            from .config.settings import Settings

            self._settings = Settings(
                config_dir=self.config_dir,
                data_dir=self.data_dir,
                app_context=self,
            )
        return self._settings

    @property
    def plugin_manager(self) -> "PluginManager":
        """
        Lazily loads and returns the PluginManager instance.
        """
        if self._plugin_manager is None:
            from .plugins.plugin_manager import PluginManager

            self._plugin_manager = PluginManager(
                state=self.state,
                storage=self.storage,
                settings=self.settings,
                app_context=self,
            )
        return self._plugin_manager

    @property
    def task_manager(self) -> "TaskManager":
        """
        Lazily loads and returns the TaskManager instance.
        """
        if self._task_manager is None:
            from .web.tasks import TaskManager

            self._task_manager = TaskManager(
                connection_manager=self.connection_manager,
            )
        return self._task_manager

    @property
    def connection_manager(self) -> "ConnectionManager":
        """
        Lazily loads and returns the ConnectionManager instance.
        """
        if self._connection_manager is None:
            from .web.websocket_manager import ConnectionManager

            self._connection_manager = ConnectionManager(
                user_provider=self.state.users.get
            )
        return self._connection_manager

    @property
    def resource_monitor(self) -> "ResourceMonitor":
        """
        Lazily loads and returns the ResourceMonitor instance.
        """
        if self._resource_monitor is None:
            from .web.resource_monitor import ResourceMonitor

            self._resource_monitor = ResourceMonitor(
                connection_manager=self.connection_manager,
                server_provider=self.get_server,
            )
        return self._resource_monitor

    @property
    def log_streamer(self) -> "LogStreamer":
        """
        Lazily loads and returns the LogStreamer instance.
        """
        if self._log_streamer is None:
            from .web.log_streamer import LogStreamer

            self._log_streamer = LogStreamer(
                connection_manager=self.connection_manager,
                log_dir=self.log_dir,
                server_provider=self.get_server,
            )
        return self._log_streamer

    @log_streamer.setter
    def log_streamer(self, value: Optional["LogStreamer"]) -> None:
        self._log_streamer = value

    @property
    def settings_service(self) -> "SettingsService":
        """Returns the SettingsService instance."""
        if self._settings_service is None:
            from .services.settings_service import SettingsService

            self._settings_service = SettingsService(
                state=self.state, storage=self.storage, settings=self.settings
            )
        return self._settings_service

    @property
    def server_service(self) -> "ServerService":
        """Returns the ServerService instance."""
        if self._server_service is None:
            from .services.server_service import ServerService

            self._server_service = ServerService(state=self.state, storage=self.storage)
        return self._server_service

    @property
    def plugin_service(self) -> "PluginService":
        """Returns the PluginService instance."""
        if self._plugin_service is None:
            from .services.plugin_service import PluginService

            self._plugin_service = PluginService(state=self.state, storage=self.storage)
        return self._plugin_service

    @property
    def user_service(self) -> "UserService":
        """Returns the UserService instance."""
        if self._user_service is None:
            from .services.user_service import UserService

            self._user_service = UserService(
                state=self.state,
                storage=self.storage,
                revoke_connections=self._revoke_user_connections,
            )
        return self._user_service

    async def _revoke_user_connections(self, username: str) -> None:
        if self._connection_manager is not None:
            await self._connection_manager.revoke_user(username)

    @property
    def bedrock_process_manager(self) -> "BedrockProcessManager":
        """
        Lazily loads and returns the BedrockProcessManager instance.
        """
        if self._bedrock_process_manager is None:
            from .core.bedrock_process_manager import BedrockProcessManager

            self._bedrock_process_manager = BedrockProcessManager(
                settings=self.settings,
                storage=self.storage,
                server_provider=self.get_server,
                api=self.api,
            )
        return self._bedrock_process_manager

    def get_server(self, server_name: str) -> "BedrockServer":
        """
        Retrieve or create a BedrockServer instance.
        """
        from .core.bedrock_server import BedrockServer

        if server_name not in self._servers:
            self._servers[server_name] = BedrockServer(
                server_name=server_name,
                settings=self.settings,
                state=self._state,
                storage=self._storage,
            )
        return self._servers[server_name]

    async def remove_server(self, server_name: str):
        """
        Stops a server, removes it from the process manager, and discards it from the context cache.
        """
        # 1. Get the server instance from the cache.
        if server_name in self._servers:
            server = self._servers[server_name]

            # 2. Stop the server if it is running.
            if await server.is_running():
                await server.stop()

            if self.loop is not None:
                await self.bedrock_process_manager.remove_server(server_name)

            # 3. Remove from the AppContext cache.
            del self._servers[server_name]
