# src/bedrock_server_manager/context.py
"""Define the central application context."""

from __future__ import annotations

import asyncio
from logging import Logger, getLogger
from typing import TYPE_CHECKING, Any, Dict, Optional

from sqlalchemy import inspect, select

from .services.lifecycle import LifecyclePhase, run_stage

if TYPE_CHECKING:
    from asyncio import AbstractEventLoop

    from .config.settings import Settings
    from .core.bedrock_process_manager import BedrockProcessManager
    from .core.bedrock_server import BedrockServer
    from .db.database import Database
    from .db.storage import Storage
    from .diagnostics.service import Diagnostics
    from .events import EventBus
    from .plugins.api_bridge import AppAPI
    from .plugins.plugin_manager import PluginManager
    from .services.metrics_service import MetricsService
    from .services.plugin_service import PluginService
    from .services.server_service import ServerService
    from .services.settings_service import SettingsService
    from .services.user_service import UserService
    from .state.app_state import AppState
    from .web.log_streamer import LogStreamer
    from .web.resource_monitor import ResourceMonitor
    from .web.runtime import WebRuntime
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
        """Initialize the AppContext."""

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
        self._metrics_service: Optional["MetricsService"] = None
        self._resource_monitor: Optional["ResourceMonitor"] = None
        self._log_streamer: Optional["LogStreamer"] = None
        self._api: Optional["AppAPI"] = None
        self._events: EventBus | None = None
        self._diagnostics: Diagnostics | None = None
        self._web_runtime: WebRuntime | None = None

        self.loop: Optional["AbstractEventLoop"] = None
        self._shutdown_task: asyncio.Task[None] | None = None
        self.lifecycle_phase = LifecyclePhase.STOPPED
        self._startup_task: asyncio.Task[None] | None = None
        self._started_components: set[str] | None = None
        self._startup_failed = False
        self._lifecycle_tasks: set[asyncio.Task] = set()

        self._servers: Dict[str, "BedrockServer"] = {}
        self.splash_txt: Optional[str] = None
        self._needs_setup: Optional[bool] = None

        self._pre_app_config_cache: Optional[Dict[str, Any]] = None
        self._settings_service: Optional["SettingsService"] = None
        self._server_service: Optional["ServerService"] = None
        self._plugin_service: Optional["PluginService"] = None
        self._user_service: Optional["UserService"] = None

    async def load(self):
        """Load the application context by initializing the settings, AppState, and
        Storage.
        """
        from . import api  # noqa: F401
        from .config.settings import Settings
        from .db.storage import Storage
        from .state.app_state import AppState

        if self.lifecycle_phase in {
            LifecyclePhase.STARTING,
            LifecyclePhase.READY,
            LifecyclePhase.STOPPING,
        }:
            raise RuntimeError("Cannot reload context while its runtime is active.")
        if any(not task.done() for task in self._lifecycle_tasks):
            raise RuntimeError("Cannot reload while lifecycle work is still running.")
        if self._diagnostics is not None and self._diagnostics.has_pending_providers:
            raise RuntimeError(
                "Cannot reload while diagnostic providers are still running."
            )
        if self._shutdown_task is not None:
            for name in (
                "_task_manager",
                "_plugin_manager",
                "_bedrock_process_manager",
                "_metrics_service",
                "_resource_monitor",
                "_log_streamer",
                "_connection_manager",
                "_events",
                "_api",
                "_diagnostics",
            ):
                setattr(self, name, None)
            self._servers.clear()
            self._shutdown_task = None
            self._startup_task = None
            self._started_components = None
            self._startup_failed = False
            self.lifecycle_phase = LifecyclePhase.STOPPED
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

        from .diagnostics.composition import configure_diagnostics

        if self._diagnostics is not None:
            await self._diagnostics.close()
        self._diagnostics = configure_diagnostics(self)
        self._storage.diagnostics = self._diagnostics

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

    async def startup(self) -> None:
        """Start runtime dependencies once; roll back partial startup on failure."""
        if self.lifecycle_phase == LifecyclePhase.READY:
            return
        if (
            self._shutdown_task is not None
            or self.lifecycle_phase == LifecyclePhase.FAILED
        ):
            raise RuntimeError("Reload the context before restarting its runtime.")
        if self._startup_task is None:
            self._startup_task = asyncio.create_task(
                self._startup_components(), name="application-startup"
            )
        await self._startup_task

    async def _startup_components(self) -> None:
        self.loop = asyncio.get_running_loop()
        self.lifecycle_phase = LifecyclePhase.STARTING
        if self._diagnostics is not None:
            self._diagnostics.start()
        self._started_components = set()
        timeout = self.settings.get("lifecycle.startup_timeout_seconds", 30.0)
        grace = self.settings.get("lifecycle.cancellation_grace_seconds", 2.0)

        async def startup_hooks() -> None:
            import os

            from .config.const import GUARD_VARIABLE

            if not os.environ.get(GUARD_VARIABLE):
                await self.events.emit("on_manager_startup", public=False)

        steps = (
            ("plugins", lambda: self.plugin_manager.load_plugins()),
            ("servers", lambda: self.bedrock_process_manager.start()),
            (
                "server discovery",
                lambda: self.api.application.update_server_statuses(request={}),
            ),
            ("resources", lambda: self.resource_monitor.start()),
            ("metrics", lambda: self.metrics_service.start()),
            ("metrics readiness", lambda: self.metrics_service.snapshot()),
            (
                "startup hooks",
                startup_hooks,
            ),
            ("plugin tasks", lambda: self.plugin_manager.start_plugin_tasks()),
            ("logs", lambda: self.log_streamer.start()),
        )
        try:
            for name, action in steps:
                self._started_components.add(name)
                await run_stage(
                    f"start {name}",
                    action,
                    timeout,
                    grace,
                    owned_tasks=self._lifecycle_tasks,
                    diagnostics=self._diagnostics,
                )
            self.lifecycle_phase = LifecyclePhase.READY
            getLogger(__name__).info("Application runtime ready.")
        except BaseException as error:
            self._startup_failed = True
            try:
                await self.shutdown()
            except BaseException as cleanup_error:
                error.add_note(f"Startup rollback also failed: {cleanup_error}")
                getLogger(__name__).error("Startup rollback failed.", exc_info=True)
            self.lifecycle_phase = LifecyclePhase.FAILED
            raise

    async def shutdown(self) -> None:
        """Finish cleanup before propagating cancellation to the caller."""
        startup = self._startup_task
        if (
            startup is not None
            and not startup.done()
            and startup is not asyncio.current_task()
        ):
            startup.cancel()
            await asyncio.wait(
                {startup},
                timeout=self.settings.get("lifecycle.shutdown_timeout_seconds", 15.0),
            )
            if startup.done() and not startup.cancelled():
                startup.exception()
        task = self._shutdown_task
        if task is asyncio.current_task():
            raise RuntimeError(
                "Application cleanup cannot recursively shut down itself."
            )
        if task is None:
            task = asyncio.create_task(
                self._shutdown_components(), name="application-shutdown"
            )
            self._shutdown_task = task
        cancelled = False
        while not task.done():
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                cancelled = True
        task.result()
        if cancelled:
            raise asyncio.CancelledError

    async def _shutdown_components(self) -> None:
        """Quiesce producers, drain operations, and persist state before disposal."""
        errors: list[Exception] = []
        self.lifecycle_phase = LifecyclePhase.STOPPING
        getLogger(__name__).info("Application runtime stopping.")
        timeout = self.settings.get("lifecycle.shutdown_timeout_seconds", 15.0)
        grace = self.settings.get("lifecycle.cancellation_grace_seconds", 2.0)
        started = self._started_components

        async def stop(name: str, action: Any, deadline: float = timeout) -> None:
            try:
                await run_stage(
                    name,
                    action,
                    deadline,
                    grace,
                    owned_tasks=self._lifecycle_tasks,
                    diagnostics=self._diagnostics if name != "close database" else None,
                )
            except (Exception, asyncio.CancelledError) as error:
                failure = (
                    error
                    if isinstance(error, Exception)
                    else RuntimeError(f"{name} cancelled")
                )
                errors.append(failure)

        if self._task_manager is not None:
            self._task_manager.begin_shutdown()
        # Observers release process and websocket dependencies before teardown.
        for name, component in (
            ("metrics", self._metrics_service),
            ("resources", self._resource_monitor),
            ("logs", self._log_streamer),
        ):
            if component is not None and (started is None or name in started):
                await stop(f"stop {name}", component.shutdown)
        if self._bedrock_process_manager is not None and (
            started is None or "servers" in started
        ):
            await stop("quiesce servers", self._bedrock_process_manager.quiesce)
        if self._plugin_manager is not None and (
            started is None or "plugins" in started
        ):
            await stop("quiesce plugins", self._plugin_manager.quiesce)
        if self._task_manager is not None:
            await stop(
                "drain operations",
                self._task_manager.shutdown,
                self.settings.get("lifecycle.task_drain_timeout_seconds", 30.0),
            )
        # Server stop hooks still have their plugins and transports available.
        if self._bedrock_process_manager is not None and (
            started is None or "servers" in started
        ):
            await stop("stop servers", self._bedrock_process_manager.shutdown)
        if self._plugin_manager is not None and (
            started is None or "plugins" in started
        ):
            await stop("unload plugins", self._plugin_manager.shutdown)
        if self._events is not None:
            await stop("drain events", self._events.close)
        if self._connection_manager is not None:
            await stop("close websockets", self._connection_manager.shutdown)
        await stop("flush state", self.flush)
        if self._diagnostics is not None:
            await self._diagnostics.close()
        if self._db is not None:
            await stop("close database", self._db.shutdown)
        self.lifecycle_phase = (
            LifecyclePhase.FAILED
            if errors or self._startup_failed
            else LifecyclePhase.STOPPED
        )
        if errors:
            raise ExceptionGroup("Application shutdown failed", errors)
        getLogger(__name__).info("Application runtime stopped.")

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
        """Read a dotted key from cached bootstrap configuration or return its default."""
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

    async def check_setup(self) -> bool:
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
            needs = bool(await _check())
            if not needs:
                self._needs_setup = False
            return needs
        except Exception as error:
            from .error import DependencyUnavailableError

            raise DependencyUnavailableError(
                "Setup status could not be determined."
            ) from error

    @property
    def needs_setup(self) -> bool:
        """Synchronous CLI adapter; async consumers use check_setup()."""
        if self._needs_setup is False:
            return False
        from .utils.general import run_async

        return bool(run_async(self.check_setup()))

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
        """Return the AppState instance."""
        if self._state is None:
            from .error import BSMError

            raise BSMError(
                "AppContext.state accessed before AppContext.load() was called."
            )
        return self._state

    @property
    def diagnostics(self) -> "Diagnostics":
        """Return diagnostics after application configuration has loaded."""
        if self._diagnostics is None:
            raise RuntimeError("Diagnostics require a loaded application context")
        return self._diagnostics

    @property
    def state_loaded(self) -> bool:
        """Whether the persistent state has been loaded into this context."""
        return self._state is not None and self._storage is not None

    @property
    def storage(self) -> "Storage":
        """Return the Storage instance."""
        if self._storage is None:
            from .error import BSMError

            raise BSMError(
                "AppContext.storage accessed before AppContext.load() was called."
            )
        return self._storage

    @property
    def settings(self) -> "Settings":
        """Return the Settings instance."""
        if self._settings is None:
            from .config.settings import Settings

            self._settings = Settings(
                config_dir=self.config_dir,
                data_dir=self.data_dir,
                app_context=self,
            )
        return self._settings

    @property
    def events(self) -> EventBus:
        """Application-owned events remain available without plugins or HTTP."""
        if self._events is None:
            from .events import EventBus, EventOptions

            options = (
                self.settings.get("events", {}) if self._settings is not None else {}
            )
            from .state_revision import revision_clock

            self._events = EventBus(
                EventOptions.model_validate(options),
                revision_provider=revision_clock.capture,
            )
            if self._diagnostics is not None:
                self._events.diagnostic_recorder = self._diagnostics.record_event
        return self._events

    @property
    def plugin_manager(self) -> "PluginManager":
        """
        Lazily loads and returns the PluginManager instance.
        """
        if self._plugin_manager is None:
            from .plugins.api_bridge import create_app_api
            from .plugins.plugin_manager import PluginManager

            self._plugin_manager = PluginManager(
                state=self.state,
                storage=self.storage,
                settings=self.settings,
                events=self.events,
                api_factory=lambda name: create_app_api(name, self),
                settings_models=self.plugin_service.settings_models,
                task_manager_provider=lambda: self._task_manager,
                connection_manager_provider=lambda: self._connection_manager,
                diagnostic_cleanup=lambda owner: self.diagnostics.remove_owner(
                    f"plugin:{owner}"
                ),
                diagnostic_failure=(
                    self._diagnostics.record_plugin_failure
                    if self._diagnostics
                    else None
                ),
                diagnostic_pending=lambda owner: self.diagnostics.owner_pending(
                    f"plugin:{owner}"
                ),
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
                diagnostics=self._diagnostics,
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
                user_provider=self.state.users.get,
                outbound_queue_limit=self.settings.get("web.outbound_queue_limit", 64),
                record_failure=(
                    self._diagnostics.record_transport_failure
                    if self._diagnostics
                    else None
                ),
            )
            from .events.websocket import attach_websocket_observer

            attach_websocket_observer(self.events, self._connection_manager)
        return self._connection_manager

    @property
    def metrics_service(self) -> "MetricsService":
        if self._metrics_service is None:
            from .services.metrics_service import MetricsService

            self._metrics_service = MetricsService(self)
        return self._metrics_service

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
                interval_provider=lambda: float(
                    self.settings.get("monitoring.bedrock_metrics_interval_sec", 3)
                ),
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
        """Return the SettingsService instance."""
        if self._settings_service is None:
            from .services.settings_service import SettingsService

            self._settings_service = SettingsService(
                state=self.state,
                storage=self.storage,
                settings=self.settings,
                plugin_service=self.plugin_service,
            )
        return self._settings_service

    @property
    def server_service(self) -> "ServerService":
        """Return the ServerService instance."""
        if self._server_service is None:
            from .services.server_service import ServerService

            self._server_service = ServerService(state=self.state, storage=self.storage)
        return self._server_service

    @property
    def plugin_service(self) -> "PluginService":
        """Return the PluginService instance."""
        if self._plugin_service is None:
            from .services.plugin_service import PluginService

            self._plugin_service = PluginService(state=self.state, storage=self.storage)
        return self._plugin_service

    @property
    def user_service(self) -> "UserService":
        """Return the UserService instance."""
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

    async def _stop_monitored_server(self, server_name: str) -> None:
        await self.api.server.stop({"server_name": server_name})

    async def _get_monitored_bans(self, server_name: str):
        from .state.models import BanItem

        response = await self.api.ban.get_server_bans({"server_name": server_name})
        return [BanItem.model_validate(item.model_dump()) for item in response.bans]

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
                events=self.events,
                stop_server=self._stop_monitored_server,
                get_bans=self._get_monitored_bans,
                record_failure=(
                    self._diagnostics.record_monitor_failure
                    if self._diagnostics is not None
                    else None
                ),
            )
        return self._bedrock_process_manager

    def get_server(
        self, server_name: str, *, require_installation: bool = True
    ) -> "BedrockServer":
        """Retrieve a registered server, rejecting invalid and unknown names."""
        from .error import ResourceNotFoundError
        from .utils.server import core_validate_server_name_format

        core_validate_server_name_format(server_name)
        if self.state.servers.get(server_name) is None:
            raise ResourceNotFoundError(f"Unknown server '{server_name}'.")
        if not require_installation:
            return self.prepare_server(server_name)
        # Recheck files even for cached handles, since an installation can disappear.
        import os

        from .error import AppFileNotFoundError

        server = self._servers.get(server_name)
        if server is None:
            import platform

            from .core.server.paths import ServerPaths

            paths = ServerPaths(
                server_name,
                self.settings.get("paths.servers"),
                self.settings.config_dir,
                platform.system(),
            )
        else:
            paths = server.paths
        for path, label in (
            (paths.bedrock_executable_path, "Server executable"),
            (paths.server_properties_path, "Server properties file"),
        ):
            if not os.path.isfile(path):
                raise AppFileNotFoundError(path, label)
        return self.prepare_server(server_name)

    def get_valid_server_names(self) -> list[str]:
        """Registered installations with an executable and server.properties."""
        from .server_validation import valid_server_names

        return valid_server_names(self.state)

    def prepare_server(self, server_name: str) -> "BedrockServer":
        """
        Create a server handle for installation or disk discovery.
        """
        from .core.bedrock_server import BedrockServer
        from .utils.server import core_validate_server_name_format

        core_validate_server_name_format(server_name)

        if server_name not in self._servers:
            self._servers[server_name] = BedrockServer(
                server_name=server_name,
                events=self.events,
                settings=self.settings,
                state=self._state,
                storage=self._storage,
            )
        return self._servers[server_name]

    async def remove_server(self, server_name: str):
        """Stop a server, removes it from the process manager, and discards it from the
        context cache.
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
