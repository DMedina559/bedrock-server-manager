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
import warnings
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple, Type

if TYPE_CHECKING:
    from ..context import AppContext

from ..config import GUARD_VARIABLE
from ..config.const import _MISSING_PARAM_PLACEHOLDER
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
        self._event_listeners: Dict[str, List[Tuple[str, Callable[..., Any]]]] = {}
        self.plugin_fastapi_routers: List[Any] = []
        self.ui_render_tags = {"json": "plugin-json-ui", "legacy": "plugin-ui-native"}
        self.plugin_static_mounts: List[tuple[str, Path, str]] = []
        self.plugin_tasks: Dict[str, List[Any]] = {}

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
        """Saves the current in-memory plugin configuration to the database asynchronously."""
        from sqlalchemy.future import select

        from ..db.models import Plugin

        async with self.app_context.db.async_session_manager() as db:
            for plugin_name, config in self.plugin_config.items():
                result = await db.execute(
                    select(Plugin).filter(Plugin.plugin_name == plugin_name)
                )
                plugin = result.scalars().first()
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
        """Dynamically imports a plugin module from the given path and retrieves the plugin class."""
        module_name_for_spec = (
            plugin_name_override if plugin_name_override else path.stem
        )
        try:
            spec = importlib.util.spec_from_file_location(module_name_for_spec, path)
            if spec is None or spec.loader is None:
                raise ImportError(
                    f"Could not create module spec for {module_name_for_spec}"
                )

            module = importlib.util.module_from_spec(spec)
            import sys

            if path.name == "__init__.py":
                package_dir = path.parent.parent
                if str(package_dir) not in sys.path:
                    sys.path.insert(0, str(package_dir))
                module.__package__ = module_name_for_spec
            else:
                module.__package__ = ""

            internal_module_name = f"bsm_plugins.{module_name_for_spec}"
            sys.modules[internal_module_name] = module
            spec.loader.exec_module(module)

            for member_name, obj in inspect.getmembers(module):
                if (
                    inspect.isclass(obj)
                    and issubclass(obj, PluginBase)
                    and obj is not PluginBase
                ):
                    return obj
        except Exception as e:
            logger.error(f"Failed to load plugin file at '{path}': {e}")
        return None

    async def shutdown(self) -> None:
        """Gracefully shuts down the PluginManager, unloading all plugins and cleaning up resources."""
        await self.unload_plugins()

    def get_native_ui_routes(self) -> List[Dict[str, str]]:
        """Returns a list of routes that are tagged for native UI rendering, including both legacy and JSON UI routes."""
        ui_routes = []
        for router in self.plugin_fastapi_routers:
            for route in router.routes:
                if not hasattr(route, "tags"):
                    continue

                if self.ui_render_tags["legacy"] in route.tags:
                    warnings.warn(
                        f"Route '{route.path}' uses legacy UI tag. Please migrate to JSON UI.",
                        DeprecationWarning,
                        stacklevel=2,
                    )

                if (
                    self.ui_render_tags["json"] in route.tags
                    or self.ui_render_tags["legacy"] in route.tags
                ):
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

        self._event_listeners.setdefault(event_name, [])
        self._event_listeners[event_name].append((listening_plugin_name, callback))

    async def dispatch_event(
        self, target_plugin: PluginBase, event_name: str, *args: Any, **kwargs: Any
    ) -> None:
        """Asynchronously dispatches an event to a specific plugin instance.

        Note: Legacy method overriding (e.g., defining `def before_server_start`)
        is no longer supported. All events must be registered using the
        `@app_event` decorator.
        """

        # Execute @app_event listeners
        for event_name_to_check in (event_name, "*"):
            listeners = self._event_listeners.get(event_name_to_check, [])
            for listener_plugin_name, callback in listeners:
                if listener_plugin_name in (
                    getattr(target_plugin, "name", None),
                    getattr(getattr(target_plugin, "api", None), "_plugin_name", None),
                ):
                    try:
                        if inspect.iscoroutinefunction(callback):
                            await callback(*args, **kwargs)
                        else:
                            callback(*args, **kwargs)
                    except Exception as e:
                        logger.error(
                            f"Error in plugin '{target_plugin.name}' handling event '{event_name}': {e}"
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
        """Asynchronously triggers a standard application event on all loaded plugins."""
        current_event_key = self._generate_event_key(event_name, **kwargs)

        # Async-safe context handling
        current_stack = _event_context_var.get() or ()

        if current_event_key in current_stack:
            return

        token = _event_context_var.set(current_stack + (current_event_key,))

        try:
            for plugin_instance in list(self.plugins):
                await self.dispatch_event(plugin_instance, event_name, *args, **kwargs)
        finally:
            # Revert the context variable
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
                        interval = float(interval_raw)

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

                        task = asyncio.create_task(run_task_loop())
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
        valid_plugin_names = set()

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

        # Scan filesystem in a background thread
        found_paths = await asyncio.to_thread(_scan_disk_for_plugins)

        # Load modules natively on the event loop
        validated_plugins = []
        for path, override_name in found_paths:
            p_name = override_name if override_name else path.stem
            p_class = self._get_plugin_class_from_path(path, override_name)
            if p_class:
                version = getattr(p_class, "version", None)
                if version and version != "N/A":
                    validated_plugins.append((p_name, p_class, str(version)))

        for plugin_name, plugin_class, version in validated_plugins:
            valid_plugin_names.add(plugin_name)
            description = plugin_class.__doc__.strip() if plugin_class.__doc__ else ""
            author = getattr(plugin_class, "author", "N/A")

            if plugin_name not in self.plugin_config:
                from ..config.const import DEFAULT_ENABLED_PLUGINS

                self.plugin_config[plugin_name] = {
                    "enabled": plugin_name in DEFAULT_ENABLED_PLUGINS,
                    "description": description,
                    "version": version,
                    "author": author,
                }
            else:
                if isinstance(self.plugin_config[plugin_name], bool):
                    self.plugin_config[plugin_name] = {
                        "enabled": self.plugin_config[plugin_name],
                        "description": description,
                        "version": version,
                        "author": author,
                    }
                else:
                    self.plugin_config[plugin_name]["description"] = description
                    self.plugin_config[plugin_name]["version"] = version
                    self.plugin_config[plugin_name]["author"] = author

                self.plugin_config[plugin_name].setdefault("enabled", False)

        plugins_to_remove = [
            p for p in self.plugin_config if p not in valid_plugin_names
        ]
        for plugin_name in plugins_to_remove:
            del self.plugin_config[plugin_name]

        await self._save_config()

    async def load_plugins(self) -> None:
        """Discovers, loads, and initializes all enabled plugins, registering their event listeners and FastAPI routers."""
        logger.info("Starting plugin loading process...")
        await self._synchronize_config_with_disk()

        if self.plugins:
            self.plugins.clear()

        self.plugin_fastapi_routers.clear()
        self.plugin_static_mounts.clear()

        def _find_enabled_plugin_paths() -> List[Tuple[str, Path]]:
            found = []
            for plugin_name, config_data in self.plugin_config.items():
                if not isinstance(config_data, dict) or not config_data.get("enabled"):
                    continue
                path = self._find_plugin_path(plugin_name)
                if path:
                    found.append((plugin_name, path))
            return found

        def _topological_sort(
            plugin_classes: Dict[str, Type[PluginBase]],
        ) -> List[str]:
            visited = set()
            temp_mark = set()
            sorted_plugins: List[str] = []

            def visit(node: str) -> bool:
                if node in temp_mark:
                    return False
                if node not in visited:
                    temp_mark.add(node)
                    p_class = plugin_classes.get(node)
                    if p_class:
                        for dep in getattr(p_class, "dependencies", []):
                            if dep not in plugin_classes or visit(dep) is False:
                                return False
                        for opt_dep in getattr(p_class, "optional_dependencies", []):
                            if opt_dep in plugin_classes and visit(opt_dep) is False:
                                return False
                    temp_mark.remove(node)
                    visited.add(node)
                    if node in plugin_classes:
                        sorted_plugins.append(node)
                return True

            for p_name in list(plugin_classes.keys()):
                if p_name not in visited:
                    if visit(p_name) is False:
                        plugin_classes.pop(p_name, None)
            return sorted_plugins

        enabled_plugin_paths = await asyncio.to_thread(_find_enabled_plugin_paths)
        enabled_plugins_data: Dict[str, Type[PluginBase]] = {}

        for plugin_name, path in enabled_plugin_paths:
            plugin_class = self._get_plugin_class_from_path(
                path, plugin_name_override=plugin_name
            )
            if plugin_class:
                enabled_plugins_data[plugin_name] = plugin_class

        sorted_plugin_names = await asyncio.to_thread(
            _topological_sort, enabled_plugins_data
        )

        for plugin_name in sorted_plugin_names:
            plugin_class = enabled_plugins_data[plugin_name]
            try:
                plugin_logger = logging.getLogger(f"plugin.{plugin_name}")
                api_instance = create_app_api(
                    plugin_name=plugin_name, app_context=self.app_context
                )

                instance = plugin_class(plugin_name, api_instance, plugin_logger)  # type: ignore
                self.plugins.append(instance)

                for method_name, method in inspect.getmembers(
                    instance, predicate=inspect.ismethod
                ):
                    event_name = getattr(method, "_app_event_name", None)
                    if event_name:
                        instance.api.listen_for_event(event_name, method)

                await self.dispatch_event(instance, "on_load")

                if hasattr(instance, "get_fastapi_routers") and callable(
                    getattr(instance, "get_fastapi_routers")
                ):
                    routers = instance.get_fastapi_routers()
                    if isinstance(routers, list):
                        self.plugin_fastapi_routers.extend(routers)

                if hasattr(instance, "get_static_mounts") and callable(
                    getattr(instance, "get_static_mounts")
                ):
                    mounts = instance.get_static_mounts()
                    if isinstance(mounts, list):
                        self.plugin_static_mounts.extend(
                            [m for m in mounts if isinstance(m, tuple) and len(m) == 3]
                        )

            except Exception as e:
                logger.error(f"Failed to instantiate plugin '{plugin_name}': {e}")

        logger.info(f"Loaded {len(self.plugins)} plugins.")

    async def unload_plugins(self) -> None:
        """Unloads all currently loaded plugins, calling their on_unload methods and cancelling any background tasks."""
        logger.info("--- Unloading all plugins ---")
        if self.plugins:
            for plugin_instance in list(self.plugins):
                await self.dispatch_event(plugin_instance, "on_unload")
                if plugin_instance.name in self.plugin_tasks:
                    for task in self.plugin_tasks.pop(plugin_instance.name):
                        task.cancel()
            self.plugins.clear()

        if self._event_listeners:
            self._event_listeners.clear()

        import sys

        for name in list(sys.modules.keys()):
            if name.startswith("bsm_plugins."):
                del sys.modules[name]

    async def reload(self) -> None:
        logger.info("--- Starting Full Plugin Reload Process ---")
        await self.unload_plugins()
        self.plugin_fastapi_routers.clear()
        self.plugin_static_mounts.clear()
        await self.load_plugins()
        logger.info("PluginManager reload complete.")
