"""Manages plugin discovery, loading, configuration, lifecycle, and event dispatch.

This module is central to the plugin architecture of the Bedrock Server Manager.
The :class:`.PluginManager` class handles all aspects of plugin interaction.
"""

import asyncio
import importlib.util
import inspect
import logging
import os
import sys
import types
import warnings
from contextlib import asynccontextmanager
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncIterator,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    Type,
)

from fastapi import APIRouter, FastAPI
from pydantic import BaseModel
from starlette.routing import BaseRoute, Route
from starlette.types import Lifespan

if TYPE_CHECKING:
    from .api_bridge import AppAPI
    from ..web.tasks import TaskManager
    from ..web.websocket_manager import ConnectionManager
    from ..state.app_state import AppState
    from ..db.storage import Storage
    from ..config.settings import Settings

from ..config import GUARD_VARIABLE
from ..config.const import DEFAULT_ENABLED_PLUGINS
from ..events import EventBus
from ..logging import log_operation_error
from ..utils.general import ReentrantAsyncLock
from ..utils.threads import run_in_thread
from .api_bridge import create_app_api
from .lifespan import RouterLifespan
from .plugin_base import PluginBase
from .runtime import PluginRuntime, PluginStatus

logger = logging.getLogger(__name__)


class PluginManager:
    """Manages the discovery, loading, configuration, and lifecycle of all plugins."""

    def __init__(
        self,
        state: "AppState",
        storage: "Storage",
        settings: "Settings",
        *,
        events: EventBus | None = None,
        api_factory: Callable[[str], "AppAPI"] | None = None,
        settings_models: dict[str, type[BaseModel]] | None = None,
        task_manager_provider: Callable[[], Optional["TaskManager"]] | None = None,
        connection_manager_provider: (
            Callable[[], Optional["ConnectionManager"]] | None
        ) = None,
    ):
        """Initialize the PluginManager with explicit required dependencies."""
        self.state = state
        self.storage = storage
        self.settings = settings
        user_plugin_dir = Path(self.settings.get("paths.plugins"))
        default_plugin_dir = Path(__file__).parent / "default"

        self.plugin_dirs: List[Path] = [user_plugin_dir, default_plugin_dir]
        logger.debug("Plugin directories configured: %s", self.plugin_dirs)

        self._lifecycle_lock = ReentrantAsyncLock()
        self._shutdown_started = False
        self.plugin_config: Dict[str, Dict[str, Any]] = {}
        self._runtime_records: dict[str, PluginRuntime] = {}
        self.plugins: List[PluginBase] = []
        self._pending_plugins: dict[str, PluginBase] = {}
        self._draining_plugins: dict[str, set[str]] = {}

        self.events = events if events is not None else EventBus()
        self.api_factory = api_factory or (
            lambda name: create_app_api(name, None, events=self.events)
        )
        self.settings_models = settings_models if settings_models is not None else {}
        self.task_manager_provider = task_manager_provider or (lambda: None)
        self.connection_manager_provider = connection_manager_provider or (lambda: None)
        self.plugin_fastapi_routers: List[APIRouter] = []
        self._router_owners: dict[str, list[APIRouter]] = {}
        self._mount_owners: dict[str, list[Tuple[str, Path, str]]] = {}
        self._mounted_routes: dict[str, list[BaseRoute]] = {}
        self._web_app: FastAPI | None = None
        self._web_lifespan_base: Lifespan[FastAPI] | None = None
        self._web_started = False
        self._web_startup_handlers: list[Callable[..., Any]] = []
        self._web_shutdown_handlers: list[Callable[..., Any]] = []
        self._router_lifespans: dict[str, RouterLifespan] = {}
        self.ui_render_tags = {"json": "plugin-json-ui", "legacy": "plugin-ui-native"}
        self.plugin_static_mounts: List[Tuple[str, Path, str]] = []
        self.plugin_tasks: Dict[str, List[asyncio.Task[Any]]] = {}

        # Cache of discovered plugin classes to avoid executing modules twice on startup
        self._discovered_classes: Dict[str, Type[PluginBase]] = {}

        # Establish synthetic parent namespace for isolated plugin imports
        if "bsm_plugins" not in sys.modules:
            synthetic_pkg = types.ModuleType("bsm_plugins")
            synthetic_pkg.__path__ = []  # Designates this module as a package
            sys.modules["bsm_plugins"] = synthetic_pkg

        for directory in self.plugin_dirs:
            try:
                directory.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                log_operation_error(
                    logger,
                    "Failed to create plugin directory %s: %s",
                    directory,
                    e,
                    error=e,
                )

        logger.debug("PluginManager initialized.")

    async def _load_config(self) -> Dict[str, Dict[str, Any]]:
        """Loads plugin configurations asynchronously via AppState."""
        return {
            name: {
                "enabled": p.enabled,
                "version": p.version,
                "author": p.author,
                "description": p.description,
            }
            for name, p in self.state.plugins.plugins.items()
        }

    async def _save_config(self) -> None:
        """Saves current plugin configuration asynchronously via AppState and Storage."""
        from ..state.models import PluginInfoState

        for plugin_name, config in self.plugin_config.items():
            p_info = PluginInfoState(
                plugin_name=plugin_name,
                enabled=bool(config.get("enabled", False)),
                version=str(config.get("version") or ""),
                author=str(config.get("author") or ""),
                description=str(config.get("description") or ""),
            )
            self.state.plugins.set(p_info)

        await self.storage.flush(self.state)

    def _find_plugin_path(self, plugin_name: str) -> Optional[Path]:
        """Searches for the plugin file or package in the configured plugin directories."""
        if (
            not plugin_name
            or ".." in plugin_name
            or "/" in plugin_name
            or "\\" in plugin_name
        ):
            logger.warning("Invalid or unsafe plugin name requested: '%s'", plugin_name)
            return None

        for p_dir in self.plugin_dirs:
            p_dir_resolved = p_dir.resolve()
            single_file_path = (p_dir_resolved / f"{plugin_name}.py").resolve()
            try:
                if single_file_path.is_relative_to(p_dir_resolved):
                    if (
                        single_file_path.is_file()
                        and not single_file_path.name.startswith("_")
                    ):
                        return single_file_path
            except ValueError:
                pass

            dir_path = (p_dir_resolved / plugin_name).resolve()
            try:
                if dir_path.is_relative_to(p_dir_resolved):
                    if dir_path.is_dir() and not dir_path.name.startswith(("_", ".")):
                        init_py_path = dir_path / "__init__.py"
                        if init_py_path.is_file():
                            return init_py_path
            except ValueError:
                pass
        return None

    def _get_plugin_class_from_path(
        self, path: Path, plugin_name_override: Optional[str] = None
    ) -> Optional[Type[PluginBase]]:
        """Dynamically imports a plugin module or package under the bsm_plugins namespace."""
        plugin_name = (
            plugin_name_override
            if plugin_name_override
            else (path.parent.name if path.name == "__init__.py" else path.stem)
        )
        full_module_name = f"bsm_plugins.{plugin_name}"
        is_package = path.name == "__init__.py"

        # Return cached class if module was already loaded
        if full_module_name in sys.modules:
            module = sys.modules[full_module_name]
            for _, obj in inspect.getmembers(module):
                if (
                    inspect.isclass(obj)
                    and issubclass(obj, PluginBase)
                    and obj is not PluginBase
                ):
                    return obj

        try:
            submodule_locations = [str(path.parent)] if is_package else None

            spec = importlib.util.spec_from_file_location(
                full_module_name,
                path,
                submodule_search_locations=submodule_locations,
            )
            if spec is None or spec.loader is None:
                raise ImportError(f"Could not create spec for '{full_module_name}'")

            module = importlib.util.module_from_spec(spec)

            sys.modules[full_module_name] = module
            spec.loader.exec_module(module)

            for _, obj in inspect.getmembers(module):
                if (
                    inspect.isclass(obj)
                    and issubclass(obj, PluginBase)
                    and obj is not PluginBase
                ):
                    return obj

            logger.warning("No PluginBase subclass found in '%s'.", path)
        except Exception as e:
            log_operation_error(
                logger, "Failed to load plugin file at '%s': %s", path, e, error=e
            )
            sys.modules.pop(full_module_name, None)
        return None

    async def quiesce(self) -> None:
        self._check_lifecycle_task()
        self._shutdown_started = True
        async with self._lifecycle_lock:
            tasks = [task for group in self.plugin_tasks.values() for task in group]
            for task in tasks:
                task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            self.plugin_tasks.clear()

    async def shutdown(self) -> None:
        """Gracefully shuts down the PluginManager, unloading all plugins and cleaning up resources."""
        await self.quiesce()
        await self.unload_plugins()

    def get_native_ui_routes(self) -> List[Dict[str, str]]:
        """Returns a list of routes that are tagged for native UI rendering."""
        ui_routes = []
        for router in self.plugin_fastapi_routers:
            for route in router.routes:
                if not isinstance(route, Route):
                    continue
                tags = getattr(route, "tags", None)
                if not tags:
                    continue

                is_legacy = self.ui_render_tags["legacy"] in tags
                is_json = self.ui_render_tags["json"] in tags

                if is_legacy:
                    warnings.warn(
                        f"Route '{route.path}' uses legacy UI tag. Please migrate to JSON UI.",
                        DeprecationWarning,
                        stacklevel=2,
                    )

                if is_json or is_legacy:
                    route_name = route.name or getattr(route, "summary", route.path)
                    ui_routes.append(
                        {"name": route_name, "path": route.path, "type": "json"}
                    )
        return ui_routes

    def register_app_event_listener(
        self, event_name: str, callback: Callable[..., Any], listening_plugin_name: str
    ) -> None:
        """Register a listener owned by the plugin's lifecycle."""
        self.events.subscribe(
            event_name, callback, owner=f"plugin:{listening_plugin_name}", active=False
        )

    @staticmethod
    def _event_owners(plugin: PluginBase) -> set[str]:
        return {
            f"plugin:{name}"
            for name in (
                getattr(getattr(plugin, "api", None), "_plugin_name", None),
                getattr(plugin, "name", None),
            )
            if name
        }

    async def dispatch_event(
        self, target_plugin: PluginBase, event_name: str, *args: Any, **kwargs: Any
    ) -> None:
        """Deliver lifecycle hooks through the bus before publishing the plugin."""
        owners = self._event_owners(target_plugin)
        if not owners:
            return
        temporary = None
        lifecycle = event_name in {"on_load", "on_unload"}
        method = getattr(target_plugin, event_name, None)
        if (
            lifecycle
            and callable(method)
            and not getattr(method, "_app_event_name", None)
            and not getattr(method, "_app_event_names", None)
        ):
            temporary = self.events.subscribe(
                event_name, method, owner=next(iter(owners)), active=False
            )
        try:
            await self.events.emit(
                event_name,
                kwargs,
                *args,
                target_owners=owners,
                strict=lifecycle,
                public=False,
            )
        finally:
            if temporary is not None:
                self.events.unsubscribe(temporary)

    async def trigger_event(self, event_name: str, *args: Any, **kwargs: Any) -> None:
        """Compatibility entry point for local plugin notifications."""
        owners = set().union(*(self._event_owners(plugin) for plugin in self.plugins))
        await self.events.emit(
            event_name, kwargs, *args, target_owners=owners, public=False
        )

    async def trigger_guarded_event(
        self, event: str, *args: Any, **kwargs: Any
    ) -> None:
        """Triggers an event only if the guard variable is not set in the environment."""
        if os.environ.get(GUARD_VARIABLE):
            return
        await self.trigger_event(event, *args, **kwargs)

    async def start_plugin_tasks(self) -> None:
        """Starts background tasks for all plugins that have methods decorated with @task_loop.

        Includes idempotency checks to prevent duplicate task loops if called multiple times.
        """
        self._check_lifecycle_task()
        async with self._lifecycle_lock:
            if self._shutdown_started:
                raise RuntimeError("Cannot start plugins during shutdown.")
            logger.debug("Starting background tasks for plugins.")
            try:
                current_loop = asyncio.get_running_loop()
            except RuntimeError:
                current_loop = None

            for plugin_instance in self.plugins:
                plugin_key = (
                    getattr(getattr(plugin_instance, "api", None), "_plugin_name", None)
                    or plugin_instance.name
                )

                # Keep only tasks that are alive AND belong to the current running event loop
                existing_tasks = self.plugin_tasks.get(plugin_key, [])
                valid_existing_tasks = [
                    t
                    for t in existing_tasks
                    if not t.done()
                    and (current_loop is None or t.get_loop() is current_loop)
                ]

                if valid_existing_tasks:
                    self.plugin_tasks[plugin_key] = valid_existing_tasks
                    continue

                # Reset task list for this plugin on the active loop
                self.plugin_tasks[plugin_key] = []

                try:
                    for method_name, method in inspect.getmembers(
                        plugin_instance, predicate=inspect.ismethod
                    ):
                        interval_raw = getattr(method, "_task_loop_interval", None)
                        if interval_raw is not None:
                            interval = max(float(interval_raw), 0.1)

                            async def run_task_loop(
                                m: Callable[..., Any] = method,
                                intv: float = interval,
                                p_name: str = plugin_key,
                                m_name: str = method_name,
                            ) -> None:
                                consecutive_failures = 0
                                while True:
                                    try:
                                        sleep_time = (
                                            intv
                                            if consecutive_failures == 0
                                            else min(
                                                intv
                                                * (2 ** min(consecutive_failures, 6)),
                                                300.0,
                                            )
                                        )
                                        await asyncio.sleep(sleep_time)
                                        if inspect.iscoroutinefunction(m):
                                            await m()
                                        else:
                                            await run_in_thread(m)
                                        consecutive_failures = 0
                                    except asyncio.CancelledError:
                                        logger.debug(
                                            "Task loop %s.%s cancelled cleanly.",
                                            p_name,
                                            m_name,
                                        )
                                        break
                                    except Exception as e:
                                        consecutive_failures += 1
                                        log_operation_error(
                                            logger,
                                            "Error in task loop %s.%s (failure #%s): %s",
                                            p_name,
                                            m_name,
                                            consecutive_failures,
                                            e,
                                            error=e,
                                        )

                            task = asyncio.create_task(
                                run_task_loop(),
                                name=f"task_loop_{plugin_key}_{method_name}",
                            )
                            self.plugin_tasks.setdefault(plugin_key, []).append(task)
                except Exception as e:
                    log_operation_error(
                        logger,
                        "Error auto-registering tasks for plugin '%s': %s",
                        plugin_key,
                        e,
                        error=e,
                    )

    async def _synchronize_config_with_disk(self) -> None:
        """Synchronizes the in-memory plugin configuration with the actual plugin files on disk."""
        self.plugin_config = await self._load_config()
        self._discovered_classes.clear()
        valid_plugin_names: Set[str] = set()

        def _scan_disk_for_plugins() -> List[Tuple[Path, Optional[str]]]:
            found: List[Tuple[Path, Optional[str]]] = []
            for directory in self.plugin_dirs:
                resolved_dir = directory.resolve()
                if not resolved_dir.exists() or not resolved_dir.is_dir():
                    continue
                for item in resolved_dir.iterdir():
                    resolved_item = item.resolve()
                    try:
                        if not resolved_item.is_relative_to(resolved_dir):
                            continue
                    except ValueError:
                        continue
                    if resolved_item.name.startswith(("_", ".")):
                        continue
                    if resolved_item.is_file() and resolved_item.suffix == ".py":
                        found.append((resolved_item, None))
                    elif (
                        resolved_item.is_dir()
                        and (resolved_item / "__init__.py").is_file()
                    ):
                        found.append(
                            (resolved_item / "__init__.py", resolved_item.name)
                        )
            return found

        found_paths = await asyncio.to_thread(_scan_disk_for_plugins)

        for path, override_name in found_paths:
            p_name = override_name if override_name else path.stem
            p_class = self._get_plugin_class_from_path(path, override_name)
            if p_class:
                version = getattr(p_class, "version", None)
                if version and version != "N/A":
                    self._discovered_classes[p_name] = p_class
                    if self.settings_models is not None:
                        models = self.settings_models
                        if p_class.settings_model is not None:
                            models[p_name] = p_class.settings_model
                        else:
                            models.pop(p_name, None)
                    valid_plugin_names.add(p_name)
                    description = p_class.__doc__.strip() if p_class.__doc__ else ""
                    author = getattr(p_class, "author", "N/A")

                    existing = self.plugin_config.get(p_name)
                    enabled_val = (
                        p_name in DEFAULT_ENABLED_PLUGINS
                        if existing is None
                        else (
                            existing
                            if isinstance(existing, bool)
                            else existing.get("enabled", False)
                        )
                    )
                    status_val = self.get_plugin_status(p_name)
                    if status_val == "UNKNOWN":
                        status_val = "DISABLED" if not enabled_val else "UNLOADED"

                    if existing is None or isinstance(existing, bool):
                        self.plugin_config[p_name] = {
                            "enabled": enabled_val,
                            "description": description,
                            "version": str(version),
                            "author": author,
                        }
                    else:
                        existing["description"] = description
                        existing["version"] = str(version)
                        existing["author"] = author
                        existing["enabled"] = enabled_val
                    self._set_runtime_status(p_name, status_val)

        plugins_to_remove = [
            p for p in self.plugin_config if p not in valid_plugin_names
        ]
        for plugin_name in plugins_to_remove:
            del self.plugin_config[plugin_name]
            if self.settings_models is not None:
                self.settings_models.pop(plugin_name, None)

        await self._save_config()

    def _sort_plugin_dependencies(
        self, plugin_classes: Dict[str, Type[PluginBase]]
    ) -> List[str]:
        """Performs a topological sort on plugins taking dependencies and optional dependencies into account."""
        visited: Set[str] = set()
        temp_mark: Set[str] = set()
        sorted_plugins: List[str] = []

        def visit(node: str) -> bool:
            if node in temp_mark:
                logger.error(
                    "Circular dependency detected involving plugin '%s'.", node
                )
                return False
            if node not in visited:
                temp_mark.add(node)
                p_class = plugin_classes.get(node)
                if p_class:
                    for dep in getattr(p_class, "dependencies", []):
                        if dep not in plugin_classes:
                            logger.error(
                                "Plugin '%s' requires missing dependency '%s'.",
                                node,
                                dep,
                            )
                            temp_mark.remove(node)
                            return False
                        if not visit(dep):
                            temp_mark.remove(node)
                            return False

                    for opt_dep in getattr(p_class, "optional_dependencies", []):
                        if opt_dep in plugin_classes and not visit(opt_dep):
                            temp_mark.remove(node)
                            return False

                temp_mark.remove(node)
                visited.add(node)
                sorted_plugins.append(node)
            return True

        for p_name in list(plugin_classes.keys()):
            if p_name not in visited:
                if not visit(p_name):
                    plugin_classes.pop(p_name, None)

        return [p for p in sorted_plugins if p in plugin_classes]

    async def load_plugins(self) -> None:
        """Discovers, loads, initializes, and starts tasks for all enabled plugins."""
        self._check_lifecycle_task()
        async with self._lifecycle_lock:
            if self._shutdown_started:
                raise RuntimeError("Cannot start plugins during shutdown.")
            logger.debug("Starting plugin loading process...")
            if self.plugins:
                await self.unload_plugins()
            await self._synchronize_config_with_disk()

            self.plugins.clear()
            self.plugin_fastapi_routers.clear()
            self.plugin_static_mounts.clear()

            # Retrieve enabled classes that were already imported during disk synchronization
            enabled_plugins_data: Dict[str, Type[PluginBase]] = {
                name: cls
                for name, cls in self._discovered_classes.items()
                if isinstance(self.plugin_config.get(name), dict)
                and self.plugin_config[name].get("enabled")
            }

            sorted_plugin_names = self._sort_plugin_dependencies(enabled_plugins_data)

            for plugin_name in sorted_plugin_names:
                if not self._can_replace_plugin(plugin_name):
                    continue
                plugin_class = enabled_plugins_data[plugin_name]
                instance = None
                try:
                    plugin_logger = logging.getLogger(f"plugin.{plugin_name}")
                    self.events.open_owner(f"plugin:{plugin_name}")
                    api_instance = self.api_factory(plugin_name)

                    instance = plugin_class(plugin_name, api_instance, plugin_logger)
                    self._pending_plugins[plugin_name] = instance
                    task_manager = self.task_manager_provider()
                    if task_manager is not None:
                        task_manager.allow_plugin(plugin_name)

                    # Support both single (_app_event_name) and stacked/multi (_app_event_names) decorators
                    for _, method in inspect.getmembers(
                        instance, predicate=inspect.ismethod
                    ):
                        event_names = getattr(method, "_app_event_names", None) or (
                            [getattr(method, "_app_event_name", None)]
                            if getattr(method, "_app_event_name", None)
                            else []
                        )
                        for event_name in event_names:
                            instance.api.listen_for_event(event_name, method)

                    # Dispatch on_load so plugins initialize internal state (e.g. self.router)
                    await self.dispatch_event(instance, "on_load")

                    if callable(getattr(instance, "get_fastapi_routers", None)):
                        routers = instance.get_fastapi_routers()
                        if isinstance(routers, list):
                            await self._register_routers(plugin_name, routers)

                    if callable(getattr(instance, "get_static_mounts", None)):
                        mounts = instance.get_static_mounts()
                        if isinstance(mounts, list):
                            valid_mounts = []
                            for m in mounts:
                                if isinstance(m, tuple) and len(m) == 3:
                                    route_path, static_dir, mount_name = m
                                    resolved_dir = Path(static_dir).resolve()
                                    # Verify resolved static dir is within one of the allowed plugin directories
                                    is_safe = False
                                    for p_dir in self.plugin_dirs:
                                        try:
                                            if resolved_dir.is_relative_to(
                                                p_dir.resolve()
                                            ):
                                                is_safe = True
                                                break
                                        except ValueError:
                                            continue
                                    if is_safe and resolved_dir.is_dir():
                                        valid_mounts.append(
                                            (route_path, resolved_dir, mount_name)
                                        )
                                    else:
                                        logger.warning(
                                            "Plugin '%s' provided invalid or out-of-bounds static mount path: '%s'",
                                            plugin_name,
                                            static_dir,
                                        )
                            self._register_mounts(plugin_name, valid_mounts)

                    self.plugins.append(instance)
                    for owner in self._event_owners(instance):
                        self.events.activate_owner(owner)
                    self._pending_plugins.pop(plugin_name, None)
                    if plugin_name in self.plugin_config:
                        self._set_runtime_status(plugin_name, "LOADED")

                except BaseException as e:
                    if instance is not None:
                        await self.unload_plugin_by_name(plugin_name)
                    else:
                        self.events.remove_owner(f"plugin:{plugin_name}")
                    if plugin_name in self.plugin_config:
                        self._set_runtime_status(plugin_name, "ERROR")
                    if not isinstance(e, Exception):
                        raise
                    log_operation_error(
                        logger,
                        "Failed to instantiate plugin '%s': %s",
                        plugin_name,
                        e,
                        error=e,
                    )

            logger.info("Loaded %s plugins.", len(self.plugins))

            # Auto-start background tasks
            await self.start_plugin_tasks()

    async def unload_plugins(self) -> None:
        """Unloads all currently loaded plugins, cleans up background tasks, and purges imported modules."""
        self._check_lifecycle_task()
        async with self._lifecycle_lock:
            logger.debug("--- Unloading all plugins ---")
            tasks_to_await: List[asyncio.Task[Any]] = []
            errors: list[Exception] = []
            for plugin_instance in reversed(list(self.plugins)):
                plugin_key = (
                    getattr(getattr(plugin_instance, "api", None), "_plugin_name", None)
                    or plugin_instance.name
                )
                try:
                    await self.unload_plugin_by_name(plugin_key)
                except Exception as error:
                    errors.append(error)

            # Cancel any remaining background tasks across all plugin keys
            for plugin_key, tasks in list(self.plugin_tasks.items()):
                for task in tasks:
                    try:
                        task.cancel()
                        tasks_to_await.append(task)
                    except Exception:
                        pass
            self.plugin_tasks.clear()

            # Ensure only tasks belonging to the current running event loop are gathered
            if tasks_to_await:
                try:
                    current_loop = asyncio.get_running_loop()
                    active_tasks = [
                        t
                        for t in tasks_to_await
                        if not t.done()
                        and (
                            t.get_loop() is current_loop or t.get_loop() == current_loop
                        )
                    ]
                    if active_tasks:
                        await asyncio.gather(*active_tasks, return_exceptions=True)
                except RuntimeError:
                    # No active running loop, tasks are already cancelled
                    pass

            for owner in list(self._runtime_records):
                self.events.remove_owner(f"plugin:{owner}")
            self._discovered_classes.clear()

            # Purge every module and submodule registered under bsm_plugins (preserve the root package)
            for name in list(sys.modules.keys()):
                if name.startswith("bsm_plugins."):
                    del sys.modules[name]
            if errors:
                raise ExceptionGroup("Plugin cleanup failed", errors)

    async def reload(self) -> None:
        """Gracefully reloads all plugins and restarts background tasks."""
        self._check_lifecycle_task()
        async with self._lifecycle_lock:
            if self._shutdown_started:
                raise RuntimeError("Cannot start plugins during shutdown.")
            logger.info("Reloading plugins.")
            await self.unload_plugins()
            self.plugin_fastapi_routers.clear()
            self.plugin_static_mounts.clear()
            await self.load_plugins()
            logger.info("PluginManager reload complete.")

    def bind_web_app(self, app: FastAPI) -> None:
        self._web_app = app
        self._web_lifespan_base = app.router.lifespan_context
        self._web_startup_handlers = list(app.router.on_startup)
        self._web_shutdown_handlers = list(app.router.on_shutdown)
        self._sync_web_routes("")

    @asynccontextmanager
    async def _web_lifespan(self, app: FastAPI) -> AsyncIterator[dict[str, Any]]:
        state: dict[str, Any] = {}
        try:
            self._check_lifecycle_task()
            async with self._lifecycle_lock:
                self._web_started = True
                for name in self._router_owners:
                    state.update(await self._start_router_lifespans(name))
            if self._web_lifespan_base is not None:
                async with self._web_lifespan_base(app) as base_state:
                    state.update(base_state or {})
                    yield state
            else:
                yield state
        except BaseException as error:
            context = getattr(app.state, "app_context", None)
            if context is not None and context._shutdown_task is None:
                context._startup_failed = True
                try:
                    await context.shutdown()
                except BaseException as cleanup_error:
                    error.add_note(
                        f"Plugin startup rollback also failed: {cleanup_error}"
                    )
            raise
        finally:
            original_error = sys.exc_info()[1]
            self._check_lifecycle_task()
            async with self._lifecycle_lock:
                self._web_started = False
                errors: list[Exception] = []
                for name in reversed(list(self._router_lifespans)):
                    try:
                        await self._close_router_lifespan(name)
                    except (Exception, asyncio.CancelledError) as error:
                        errors.append(
                            error
                            if isinstance(error, Exception)
                            else RuntimeError("Plugin router cleanup cancelled")
                        )
                if errors:
                    failure = ExceptionGroup(
                        "Plugin router lifespan cleanup failed", errors
                    )
                    if original_error is not None:
                        original_error.add_note(str(failure))
                        logger.error("Plugin router cleanup also failed: %s", failure)
                    else:
                        raise failure

    def _check_lifecycle_task(self) -> None:
        if any(
            owner.task is asyncio.current_task()
            for owner in self._router_lifespans.values()
        ):
            raise RuntimeError(
                "Router lifespans cannot recursively change plugin lifecycle."
            )

    async def _start_router_lifespans(self, name: str) -> dict[str, Any]:
        if name in self._router_lifespans or self._web_app is None:
            return {}
        owner = RouterLifespan(
            self._web_app,
            self._router_owners.get(name, []),
            timeout=(self.settings.get("lifecycle.plugin_timeout_seconds", 10.0)),
            grace=(self.settings.get("lifecycle.cancellation_grace_seconds", 2.0)),
        )
        self._router_lifespans[name] = owner
        try:
            return await owner.start()
        except BaseException:
            self._router_lifespans.pop(name, None)
            raise

    async def _close_router_lifespan(self, name: str) -> None:
        owner = self._router_lifespans.get(name)
        if owner is not None:
            try:
                await owner.close()
            finally:
                if owner.task.done():
                    self._router_lifespans.pop(name, None)

    async def _register_routers(self, name: str, routers: list[APIRouter]) -> None:
        self._router_owners.setdefault(name, []).extend(routers)
        self.plugin_fastapi_routers.extend(routers)
        if self._web_started:
            await self._start_router_lifespans(name)
        self._sync_web_routes(name)

    def _register_mounts(self, name: str, mounts: list[Tuple[str, Path, str]]) -> None:
        self._mount_owners.setdefault(name, []).extend(mounts)
        self.plugin_static_mounts.extend(mounts)
        self._sync_web_routes(name)

    def _remove_web_routes(self, name: str) -> None:
        routes = self._mounted_routes.pop(name, [])
        if self._web_app is not None:
            self._web_app.router.routes[:] = [
                route for route in self._web_app.router.routes if route not in routes
            ]
            self._web_app.openapi_schema = None

    def _sync_web_routes(self, name: str) -> None:
        if self._web_app is None:
            return
        for owner in list(self._mounted_routes):
            self._remove_web_routes(owner)
        self._web_app.router.lifespan_context = self._web_lifespan
        from fastapi.staticfiles import StaticFiles

        for owner in dict.fromkeys([*self._router_owners, *self._mount_owners]):
            before = {id(route) for route in self._web_app.router.routes}
            try:
                for router in self._router_owners.get(owner, []):
                    self._web_app.include_router(router)
                for path, directory, mount_name in self._mount_owners.get(owner, []):
                    self._web_app.mount(
                        path, StaticFiles(directory=directory), name=mount_name
                    )
            finally:
                self._mounted_routes[owner] = [
                    route
                    for route in self._web_app.router.routes
                    if id(route) not in before
                ]
                self._web_app.openapi_schema = None
                self._web_app.router.lifespan_context = self._web_lifespan
                self._web_app.router.on_startup[:] = self._web_startup_handlers
                self._web_app.router.on_shutdown[:] = self._web_shutdown_handlers

    def _set_runtime_status(self, plugin_name: str, status: PluginStatus) -> None:
        self._runtime_records[plugin_name] = PluginRuntime(
            plugin_name=plugin_name,
            status=status,
            module_name=f"bsm_plugins.{plugin_name}" if status == "LOADED" else None,
        )

    def get_plugin_runtime(self, plugin_name: str) -> PluginRuntime:
        record = self._runtime_records.get(plugin_name) or PluginRuntime(
            plugin_name=plugin_name, status=self.get_plugin_status(plugin_name)
        )
        data = record.model_dump()
        data["registered_events"] = self.events.events_for_owner(
            f"plugin:{plugin_name}"
        )
        data["active_tasks"] = [
            task.get_name()
            for task in self.plugin_tasks.get(plugin_name, [])
            if not task.done()
        ]
        return PluginRuntime.model_validate(data)

    def get_plugin_status(self, plugin_name: str) -> PluginStatus:
        """Returns the runtime status of a given plugin ('LOADED', 'DISABLED', 'ERROR', or 'UNLOADED')."""
        cfg = self.plugin_config.get(plugin_name)
        is_loaded = any(
            p.name == plugin_name
            or getattr(getattr(p, "api", None), "_plugin_name", None) == plugin_name
            for p in self.plugins
        )
        if is_loaded:
            return "LOADED"
        if plugin_name in self._runtime_records:
            return self._runtime_records[plugin_name].status
        if isinstance(cfg, dict):
            if cfg.get("status") in ("ERROR", "DISABLED", "UNLOADED"):
                return PluginRuntime(
                    plugin_name=plugin_name, status=cfg["status"]
                ).status
            if not cfg.get("enabled", False):
                return "DISABLED"
        return "UNKNOWN" if cfg is None else "UNLOADED"

    async def unload_plugin_by_name(self, plugin_name: str) -> bool:
        """Unloads a single plugin by name, stopping its tasks and unregistering its listeners."""
        self._check_lifecycle_task()
        async with self._lifecycle_lock:
            target_instance = self._pending_plugins.get(plugin_name)
            for p in self.plugins:
                api = getattr(p, "api", None)
                ident = getattr(api, "_plugin_name", None) or getattr(p, "name", None)
                if p.name == plugin_name or ident == plugin_name:
                    target_instance = p
                    break

            if not target_instance:
                logger.warning("Plugin '%s' is not currently loaded.", plugin_name)
                if plugin_name in self.plugin_config:
                    self._set_runtime_status(plugin_name, "UNLOADED")
                return False

            plugin_key = (
                getattr(getattr(target_instance, "api", None), "_plugin_name", None)
                or target_instance.name
            )

            if asyncio.current_task() in self.plugin_tasks.get(plugin_key, []):
                raise RuntimeError("A plugin task cannot unload its own plugin.")
            tasks_to_await = []
            if plugin_key in self.plugin_tasks:
                for task in self.plugin_tasks.pop(plugin_key, []):
                    task.cancel()
                    tasks_to_await.append(task)

            if tasks_to_await:
                try:
                    current_loop = asyncio.get_running_loop()
                    active_tasks = [
                        t
                        for t in tasks_to_await
                        if not t.done() and t.get_loop() is current_loop
                    ]
                    if active_tasks:
                        await asyncio.gather(*active_tasks, return_exceptions=True)
                except RuntimeError:
                    pass

            task_manager = self.task_manager_provider()
            if task_manager is not None:
                await task_manager.drain_plugin(plugin_key)

            unload_errors: list[Exception] = []
            try:
                timeout = self.settings.get("lifecycle.plugin_timeout_seconds", 10.0)
                async with asyncio.timeout(timeout):
                    for owner in self._event_owners(target_instance):
                        self.events.deactivate_owner(owner)
                        await self.events.drain_owner(owner, timeout)
                    await self.dispatch_event(target_instance, "on_unload")
            except Exception as e:
                unload_errors.append(e)
                log_operation_error(
                    logger,
                    "Error during on_unload for '%s': %s",
                    plugin_key,
                    e,
                    error=e,
                )

            owners = set(self._event_owners(target_instance))
            if any(self.events.owner_pending(owner) for owner in owners):
                self._draining_plugins[plugin_key] = owners
            self._pending_plugins.pop(plugin_key, None)
            if target_instance in self.plugins:
                self.plugins.remove(target_instance)

            try:
                await self._close_router_lifespan(plugin_key)
            except Exception as error:
                unload_errors.append(error)
                logger.exception("Router lifespan cleanup failed for %s", plugin_key)
            self._remove_web_routes(plugin_key)
            for router in self._router_owners.pop(plugin_key, []):
                if router in self.plugin_fastapi_routers:
                    self.plugin_fastapi_routers.remove(router)
            for mount in self._mount_owners.pop(plugin_key, []):
                if mount in self.plugin_static_mounts:
                    self.plugin_static_mounts.remove(mount)

            self._sync_web_routes(plugin_key)
            for owner in self._event_owners(target_instance):
                self.events.remove_owner(owner)

            cm = self.connection_manager_provider()
            if cm is not None:
                cm.unregister_plugin_providers(plugin_key)
                cm.unregister_plugin_providers(target_instance.name)
                cm.unregister_plugin_providers(plugin_name)

            full_module_name = f"bsm_plugins.{plugin_name}"
            sys.modules.pop(full_module_name, None)

            if plugin_name in self.plugin_config:
                self._set_runtime_status(plugin_name, "UNLOADED")

            if unload_errors and self._shutdown_started:
                raise ExceptionGroup(
                    f"Plugin '{plugin_key}' cleanup failed", unload_errors
                )
            if unload_errors:
                self._set_runtime_status(plugin_name, "ERROR")
                return False
            logger.info("Plugin '%s' unloaded successfully.", plugin_name)
            return True

    def _can_replace_plugin(self, plugin_name: str) -> bool:
        owners = self._draining_plugins.get(plugin_name, set())
        if any(self.events.owner_pending(owner) for owner in owners):
            self._set_runtime_status(plugin_name, "ERROR")
            logger.warning(
                "Plugin '%s' is still draining its old event generation", plugin_name
            )
            return False
        self._draining_plugins.pop(plugin_name, None)
        return True

    async def load_plugin_by_name(self, plugin_name: str) -> bool:
        """Loads and initializes a single plugin by name if discoverable."""
        self._check_lifecycle_task()
        async with self._lifecycle_lock:
            if self._shutdown_started:
                raise RuntimeError("Cannot start plugins during shutdown.")
            if not self._can_replace_plugin(plugin_name):
                return False
            for p in self.plugins:
                api = getattr(p, "api", None)
                ident = getattr(api, "_plugin_name", None) or getattr(p, "name", None)
                if p.name == plugin_name or ident == plugin_name:
                    logger.debug("Plugin '%s' is already loaded.", plugin_name)
                    return True

            path = self._find_plugin_path(plugin_name)
            if not path:
                logger.error(
                    "Cannot load plugin '%s': File or directory not found.", plugin_name
                )
                if plugin_name in self.plugin_config:
                    self._set_runtime_status(plugin_name, "ERROR")
                return False

            p_class = self._get_plugin_class_from_path(path, plugin_name)
            if not p_class:
                logger.error(
                    "Cannot load plugin '%s': No PluginBase subclass found.",
                    plugin_name,
                )
                if plugin_name in self.plugin_config:
                    self._set_runtime_status(plugin_name, "ERROR")
                return False

            if self.settings_models is not None:
                models = self.settings_models
                if p_class.settings_model is not None:
                    models[plugin_name] = p_class.settings_model
                else:
                    models.pop(plugin_name, None)
            instance = None
            try:
                plugin_logger = logging.getLogger(f"plugin.{plugin_name}")
                self.events.open_owner(f"plugin:{plugin_name}")
                api_instance = self.api_factory(plugin_name)

                instance = p_class(plugin_name, api_instance, plugin_logger)
                self._pending_plugins[plugin_name] = instance
                task_manager = self.task_manager_provider()
                if task_manager is not None:
                    task_manager.allow_plugin(plugin_name)

                for _, method in inspect.getmembers(
                    instance, predicate=inspect.ismethod
                ):
                    event_names = getattr(method, "_app_event_names", None) or (
                        [getattr(method, "_app_event_name", None)]
                        if getattr(method, "_app_event_name", None)
                        else []
                    )
                    for event_name in event_names:
                        instance.api.listen_for_event(event_name, method)

                await self.dispatch_event(instance, "on_load")

                if callable(getattr(instance, "get_fastapi_routers", None)):
                    routers = instance.get_fastapi_routers()
                    if isinstance(routers, list):
                        await self._register_routers(plugin_name, routers)

                if callable(getattr(instance, "get_static_mounts", None)):
                    mounts = instance.get_static_mounts()
                    if isinstance(mounts, list):
                        for m in mounts:
                            if isinstance(m, tuple) and len(m) == 3:
                                route_path, static_dir, mount_name = m
                                resolved_dir = Path(static_dir).resolve()
                                is_safe = False
                                for p_dir in self.plugin_dirs:
                                    try:
                                        if resolved_dir.is_relative_to(p_dir.resolve()):
                                            is_safe = True
                                            break
                                    except ValueError:
                                        continue
                                if is_safe and resolved_dir.is_dir():
                                    self._register_mounts(
                                        plugin_name,
                                        [(route_path, resolved_dir, mount_name)],
                                    )

                for method_name, method in inspect.getmembers(
                    instance, predicate=inspect.ismethod
                ):
                    interval_raw = getattr(method, "_task_loop_interval", None)
                    if interval_raw is not None:
                        interval = max(float(interval_raw), 0.1)

                        async def run_task_loop(
                            m: Callable[..., Any] = method,
                            intv: float = interval,
                            p_name: str = plugin_name,
                            m_name: str = method_name,
                        ) -> None:
                            consecutive_failures = 0
                            while True:
                                try:
                                    sleep_time = (
                                        intv
                                        if consecutive_failures == 0
                                        else min(
                                            intv * (2 ** min(consecutive_failures, 6)),
                                            300.0,
                                        )
                                    )
                                    await asyncio.sleep(sleep_time)
                                    if inspect.iscoroutinefunction(m):
                                        await m()
                                    else:
                                        await run_in_thread(m)
                                    consecutive_failures = 0
                                except asyncio.CancelledError:
                                    logger.debug(
                                        "Task loop %s.%s cancelled cleanly.",
                                        p_name,
                                        m_name,
                                    )
                                    break
                                except Exception as e:
                                    consecutive_failures += 1
                                    log_operation_error(
                                        logger,
                                        "Error in task loop %s.%s (failure #%s): %s",
                                        p_name,
                                        m_name,
                                        consecutive_failures,
                                        e,
                                        error=e,
                                    )

                        task = asyncio.create_task(
                            run_task_loop(),
                            name=f"task_loop_{plugin_name}_{method_name}",
                        )
                        self.plugin_tasks.setdefault(plugin_name, []).append(task)

                self.plugins.append(instance)
                for owner in self._event_owners(instance):
                    self.events.activate_owner(owner)
                self._pending_plugins.pop(plugin_name, None)
                if plugin_name in self.plugin_config:
                    self._set_runtime_status(plugin_name, "LOADED")
                logger.debug("Plugin '%s' loaded successfully.", plugin_name)
                return True
            except BaseException as e:
                if instance is not None:
                    await self.unload_plugin_by_name(plugin_name)
                else:
                    self.events.remove_owner(f"plugin:{plugin_name}")
                if not isinstance(e, Exception):
                    raise
                log_operation_error(
                    logger, "Failed to load plugin '%s': %s", plugin_name, e, error=e
                )
                if plugin_name in self.plugin_config:
                    self._set_runtime_status(plugin_name, "ERROR")
                return False

    async def reload_plugin(self, plugin_name: str) -> bool:
        """Reloads a single plugin by name."""
        self._check_lifecycle_task()
        async with self._lifecycle_lock:
            if self._shutdown_started:
                raise RuntimeError("Cannot start plugins during shutdown.")
            logger.info("Reloading plugin '%s'...", plugin_name)
            loaded = (
                any(
                    (
                        getattr(getattr(plugin, "api", None), "_plugin_name", None)
                        or plugin.name
                    )
                    == plugin_name
                    for plugin in self.plugins
                )
                or plugin_name in self._pending_plugins
            )
            if loaded and not await self.unload_plugin_by_name(plugin_name):
                return False
            return await self.load_plugin_by_name(plugin_name)

    async def enable_plugin(
        self, plugin_name: str, load_immediately: bool = True
    ) -> bool:
        """Enables a plugin in config and optionally loads it immediately."""
        self._check_lifecycle_task()
        async with self._lifecycle_lock:
            if self._shutdown_started:
                raise RuntimeError("Cannot start plugins during shutdown.")
            await self._synchronize_config_with_disk()
            if plugin_name not in self.plugin_config:
                logger.error("Cannot enable unknown plugin '%s'.", plugin_name)
                return False

            self.plugin_config[plugin_name]["enabled"] = True
            await self._save_config()

            if load_immediately:
                return await self.load_plugin_by_name(plugin_name)
            self._set_runtime_status(plugin_name, "UNLOADED")
            return True

    async def disable_plugin(
        self, plugin_name: str, unload_immediately: bool = True
    ) -> bool:
        """Disables a plugin in config and optionally unloads it immediately."""
        self._check_lifecycle_task()
        async with self._lifecycle_lock:
            await self._synchronize_config_with_disk()
            if plugin_name not in self.plugin_config:
                logger.error("Cannot disable unknown plugin '%s'.", plugin_name)
                return False

            self.plugin_config[plugin_name]["enabled"] = False
            await self._save_config()

            if unload_immediately:
                await self.unload_plugin_by_name(plugin_name)
            self._set_runtime_status(plugin_name, "DISABLED")
            return True
