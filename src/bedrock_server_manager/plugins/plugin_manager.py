"""Manages plugin discovery, loading, configuration, lifecycle, and event dispatch.

This module is central to the plugin architecture of the Bedrock Server Manager.
The :class:`.PluginManager` class handles all aspects of plugin interaction.
"""

import asyncio
import contextvars
import importlib.util
import inspect
import logging
import os
import sys
import types
import warnings
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Set, Tuple, Type

if TYPE_CHECKING:
    from ..context import AppContext

from ..config import GUARD_VARIABLE
from ..config.const import _MISSING_PARAM_PLACEHOLDER, DEFAULT_ENABLED_PLUGINS
from .api_bridge import create_app_api
from .event_trigger import _event_registry
from .plugin_base import PluginBase

logger = logging.getLogger(__name__)

# ContextVars are the async-safe alternative to threading.local()
_event_context_var: contextvars.ContextVar[Optional[Tuple[str, ...]]] = (
    contextvars.ContextVar("_event_context_var", default=None)
)


class PluginManager:
    """Manages the discovery, loading, configuration, and lifecycle of all plugins."""

    def __init__(self, app_context: "AppContext"):
        """Initialize the PluginManager with the given application context."""
        self.app_context = app_context
        self.settings = app_context.settings
        user_plugin_dir = Path(self.settings.get("paths.plugins"))
        default_plugin_dir = Path(__file__).parent / "default"

        self.plugin_dirs: List[Path] = [user_plugin_dir, default_plugin_dir]
        logger.debug(f"Plugin directories configured: {self.plugin_dirs}")

        self.plugin_config: Dict[str, Dict[str, Any]] = {}
        self.plugins: List[PluginBase] = []

        # Event listener map structured as: {event_name: {plugin_name: [callbacks]}}
        self._event_listeners: Dict[str, Dict[str, List[Callable[..., Any]]]] = {}
        self.plugin_fastapi_routers: List[Any] = []
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
                logger.error(f"Failed to create plugin directory {directory}: {e}")

        logger.info("PluginManager initialized.")

    async def _load_config(self) -> Dict[str, Dict[str, Any]]:
        """Loads plugin configurations from the database asynchronously."""
        from sqlalchemy.future import select

        from ..db.models import Plugin

        async with self.app_context.db.async_session_manager() as db:
            result = await db.execute(select(Plugin))
            plugins = result.scalars().all()
            return {
                plugin.plugin_name: {
                    "enabled": plugin.enabled,
                    "version": plugin.version,
                    "author": plugin.author,
                    "description": plugin.description,
                }
                for plugin in plugins
            }

    async def _save_config(self) -> None:
        """Saves the current in-memory plugin configuration to the database in a single batch."""
        from sqlalchemy.future import select

        from ..db.models import Plugin

        async with self.app_context.db.async_session_manager() as db:
            result = await db.execute(select(Plugin))
            existing_plugins = {p.plugin_name: p for p in result.scalars().all()}

            for plugin_name, config in self.plugin_config.items():
                plugin = existing_plugins.get(plugin_name)
                if plugin:
                    plugin.enabled = config.get("enabled", False)
                    plugin.version = config.get("version")
                    plugin.author = config.get("author")
                    plugin.description = config.get("description")
                else:
                    plugin = Plugin(
                        plugin_name=plugin_name,
                        enabled=config.get("enabled", False),
                        version=config.get("version"),
                        author=config.get("author"),
                        description=config.get("description"),
                    )
                    db.add(plugin)
            await db.commit()

    def _find_plugin_path(self, plugin_name: str) -> Optional[Path]:
        """Searches for the plugin file or package in the configured plugin directories."""
        for p_dir in self.plugin_dirs:
            single_file_path = p_dir / f"{plugin_name}.py"
            if single_file_path.is_file() and not single_file_path.name.startswith("_"):
                return single_file_path

            dir_path = p_dir / plugin_name
            if dir_path.is_dir() and not dir_path.name.startswith(("_", ".")):
                init_py_path = dir_path / "__init__.py"
                if init_py_path.is_file():
                    return init_py_path
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
            # submodule_search_locations allows Python to resolve relative package imports
            # without requiring global sys.path mutation
            submodule_locations = [str(path.parent)] if is_package else None

            spec = importlib.util.spec_from_file_location(
                full_module_name,
                path,
                submodule_search_locations=submodule_locations,
            )
            if spec is None or spec.loader is None:
                raise ImportError(f"Could not create spec for '{full_module_name}'")

            module = importlib.util.module_from_spec(spec)

            # Register before execution so circular and relative sub-imports resolve properly
            sys.modules[full_module_name] = module
            spec.loader.exec_module(module)

            for _, obj in inspect.getmembers(module):
                if (
                    inspect.isclass(obj)
                    and issubclass(obj, PluginBase)
                    and obj is not PluginBase
                ):
                    return obj

            logger.warning(f"No PluginBase subclass found in '{path}'.")
        except Exception as e:
            logger.error(f"Failed to load plugin file at '{path}': {e}", exc_info=True)
            sys.modules.pop(full_module_name, None)
        return None

    async def shutdown(self) -> None:
        """Gracefully shuts down the PluginManager, unloading all plugins and cleaning up resources."""
        await self.unload_plugins()

    def get_native_ui_routes(self) -> List[Dict[str, str]]:
        """Returns a list of routes that are tagged for native UI rendering."""
        ui_routes = []
        for router in self.plugin_fastapi_routers:
            for route in router.routes:
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
        """Registers a callback function to listen for a specific application event."""
        if not callable(callback):
            logger.error(
                f"Plugin '{listening_plugin_name}' attempted to register a non-callable listener."
            )
            return

        plugin_map = self._event_listeners.setdefault(event_name, {})
        plugin_map.setdefault(listening_plugin_name, []).append(callback)

    async def dispatch_event(
        self, target_plugin: PluginBase, event_name: str, *args: Any, **kwargs: Any
    ) -> None:
        """Asynchronously dispatches an event to a specific plugin instance in O(1) lookup."""
        plugin_name = getattr(target_plugin, "name", None) or getattr(
            getattr(target_plugin, "api", None), "_plugin_name", None
        )

        if not plugin_name:
            return

        for name in (event_name, "*"):
            listeners = self._event_listeners.get(name, {}).get(plugin_name, [])
            for callback in listeners:
                try:
                    if inspect.iscoroutinefunction(callback):
                        await callback(*args, **kwargs)
                    else:
                        callback(*args, **kwargs)
                except Exception as e:
                    logger.error(
                        f"Error in plugin '{plugin_name}' handling event '{event_name}': {e}"
                    )

    def _generate_event_key(self, event_name: str, **kwargs: Any) -> str:
        """Generates a unique key for the event based on its name and identity parameters."""
        identity_key_names = _event_registry.get(event_name)
        if not identity_key_names:
            return event_name
        return "|".join(
            (
                event_name,
                *(
                    str(kwargs.get(k, _MISSING_PARAM_PLACEHOLDER))
                    for k in identity_key_names
                ),
            )
        )

    async def trigger_event(self, event_name: str, *args: Any, **kwargs: Any) -> None:
        """Asynchronously triggers an event on all loaded plugins."""
        current_event_key = self._generate_event_key(event_name, **kwargs)
        current_stack = _event_context_var.get() or ()

        if current_event_key in current_stack:
            return

        token = _event_context_var.set(current_stack + (current_event_key,))
        try:
            for plugin_instance in list(self.plugins):
                await self.dispatch_event(plugin_instance, event_name, *args, **kwargs)
        finally:
            _event_context_var.reset(token)

    async def trigger_guarded_event(
        self, event: str, *args: Any, **kwargs: Any
    ) -> None:
        """Triggers an event only if the guard variable is not set in the environment."""
        if os.environ.get(GUARD_VARIABLE):
            return
        await self.trigger_event(event, *args, **kwargs)

    async def start_plugin_tasks(self) -> None:
        """Starts background tasks for all plugins that have methods decorated with @task_loop."""
        logger.info("Starting background tasks for plugins.")
        for plugin_instance in self.plugins:
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
                            p_name: str = plugin_instance.name,
                            m_name: str = method_name,
                        ) -> None:
                            while True:
                                try:
                                    await asyncio.sleep(intv)
                                    if inspect.iscoroutinefunction(m):
                                        await m()
                                    else:
                                        await asyncio.to_thread(m)
                                except asyncio.CancelledError:
                                    break
                                except Exception as e:
                                    logger.error(
                                        f"Error in task loop {p_name}.{m_name}: {e}"
                                    )

                        task = asyncio.create_task(
                            run_task_loop(),
                            name=f"task_loop_{plugin_instance.name}_{method_name}",
                        )
                        self.plugin_tasks.setdefault(plugin_instance.name, []).append(
                            task
                        )
            except Exception as e:
                logger.error(
                    f"Error auto-registering tasks for plugin '{plugin_instance.name}': {e}"
                )

    async def _synchronize_config_with_disk(self) -> None:
        """Synchronizes the in-memory plugin configuration with the actual plugin files on disk."""
        self.plugin_config = await self._load_config()
        self._discovered_classes.clear()
        valid_plugin_names: Set[str] = set()

        def _scan_disk_for_plugins() -> List[Tuple[Path, Optional[str]]]:
            found: List[Tuple[Path, Optional[str]]] = []
            for directory in self.plugin_dirs:
                if not directory.exists() or not directory.is_dir():
                    continue
                for item in directory.iterdir():
                    if item.name.startswith("__"):
                        continue
                    if item.is_file() and item.suffix == ".py":
                        found.append((item, None))
                    elif item.is_dir() and (item / "__init__.py").is_file():
                        found.append((item / "__init__.py", item.name))
            return found

        found_paths = await asyncio.to_thread(_scan_disk_for_plugins)

        for path, override_name in found_paths:
            p_name = override_name if override_name else path.stem
            p_class = self._get_plugin_class_from_path(path, override_name)
            if p_class:
                version = getattr(p_class, "version", None)
                if version and version != "N/A":
                    self._discovered_classes[p_name] = p_class
                    valid_plugin_names.add(p_name)
                    description = p_class.__doc__.strip() if p_class.__doc__ else ""
                    author = getattr(p_class, "author", "N/A")

                    existing = self.plugin_config.get(p_name)
                    if existing is None:
                        self.plugin_config[p_name] = {
                            "enabled": p_name in DEFAULT_ENABLED_PLUGINS,
                            "description": description,
                            "version": str(version),
                            "author": author,
                        }
                    elif isinstance(existing, bool):
                        self.plugin_config[p_name] = {
                            "enabled": existing,
                            "description": description,
                            "version": str(version),
                            "author": author,
                        }
                    else:
                        existing["description"] = description
                        existing["version"] = str(version)
                        existing["author"] = author
                        existing.setdefault("enabled", False)

        plugins_to_remove = [
            p for p in self.plugin_config if p not in valid_plugin_names
        ]
        for plugin_name in plugins_to_remove:
            del self.plugin_config[plugin_name]

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
                logger.error(f"Circular dependency detected involving plugin '{node}'.")
                return False
            if node not in visited:
                temp_mark.add(node)
                p_class = plugin_classes.get(node)
                if p_class:
                    for dep in getattr(p_class, "dependencies", []):
                        if dep not in plugin_classes:
                            logger.error(
                                f"Plugin '{node}' requires missing dependency '{dep}'."
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
        """Discovers, loads, and initializes all enabled plugins."""
        logger.info("Starting plugin loading process...")
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
            plugin_class = enabled_plugins_data[plugin_name]
            try:
                plugin_logger = logging.getLogger(f"plugin.{plugin_name}")
                api_instance = create_app_api(
                    plugin_name=plugin_name, app_context=self.app_context
                )

                instance = plugin_class(plugin_name, api_instance, plugin_logger)
                self.plugins.append(instance)

                for _, method in inspect.getmembers(
                    instance, predicate=inspect.ismethod
                ):
                    event_name = getattr(method, "_app_event_name", None)
                    if event_name:
                        instance.api.listen_for_event(event_name, method)

                await self.dispatch_event(instance, "on_load")

                if callable(getattr(instance, "get_fastapi_routers", None)):
                    routers = instance.get_fastapi_routers()
                    if isinstance(routers, list):
                        self.plugin_fastapi_routers.extend(routers)

                if callable(getattr(instance, "get_static_mounts", None)):
                    mounts = instance.get_static_mounts()
                    if isinstance(mounts, list):
                        self.plugin_static_mounts.extend(
                            [m for m in mounts if isinstance(m, tuple) and len(m) == 3]
                        )

            except Exception as e:
                logger.error(f"Failed to instantiate plugin '{plugin_name}': {e}")

        logger.info(f"Loaded {len(self.plugins)} plugins.")

    async def unload_plugins(self) -> None:
        """Unloads all currently loaded plugins, cleans up background tasks, and purges imported modules."""
        logger.info("--- Unloading all plugins ---")
        tasks_to_await: List[asyncio.Task[Any]] = []

        if self.plugins:
            for plugin_instance in list(self.plugins):
                try:
                    await self.dispatch_event(plugin_instance, "on_unload")
                except Exception as e:
                    logger.error(
                        f"Error during on_unload for '{plugin_instance.name}': {e}"
                    )

                if plugin_instance.name in self.plugin_tasks:
                    for task in self.plugin_tasks.pop(plugin_instance.name):
                        task.cancel()
                        tasks_to_await.append(task)

            self.plugins.clear()

        # Ensure all cancelled tasks finish terminating cleanly
        if tasks_to_await:
            await asyncio.gather(*tasks_to_await, return_exceptions=True)

        self._event_listeners.clear()
        self._discovered_classes.clear()

        # Purge every module and submodule registered under bsm_plugins (preserve the root package)
        for name in list(sys.modules.keys()):
            if name.startswith("bsm_plugins."):
                del sys.modules[name]

    async def reload(self) -> None:
        """Gracefully reloads all plugins and restarts background tasks."""
        logger.info("--- Starting Full Plugin Reload Process ---")
        await self.unload_plugins()
        self.plugin_fastapi_routers.clear()
        self.plugin_static_mounts.clear()
        await self.load_plugins()
        await self.start_plugin_tasks()
        logger.info("PluginManager reload complete.")
