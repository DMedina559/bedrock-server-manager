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

        # Event listener map structured as: {event_name: {plugin_identifier: [callbacks]}}
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
        """Loads plugin configurations asynchronously via AppState and Storage."""
        await self.app_context.storage.load_state(self.app_context.state)
        return {
            name: {
                "enabled": p.enabled,
                "version": p.version,
                "author": p.author,
                "description": p.description,
            }
            for name, p in self.app_context.state.plugins.plugins.items()
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
            self.app_context.state.plugins.set(p_info)

        await self.app_context.storage.flush(self.app_context.state)

    def _find_plugin_path(self, plugin_name: str) -> Optional[Path]:
        """Searches for the plugin file or package in the configured plugin directories."""
        if (
            not plugin_name
            or ".." in plugin_name
            or "/" in plugin_name
            or "\\" in plugin_name
        ):
            logger.warning(f"Invalid or unsafe plugin name requested: '{plugin_name}'")
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
        """Asynchronously dispatches an event to a specific plugin instance.

        Checks both internal slug (api._plugin_name) and display name (target_plugin.name)
        to ensure listeners are reliably found. Synchronous callbacks are executed off the
        event loop via asyncio.to_thread. Internal context references (e.g. app_context)
        are filtered out to prevent context leakage.
        """
        target_identifiers: Set[str] = set()

        api = getattr(target_plugin, "api", None)
        if api and getattr(api, "_plugin_name", None):
            target_identifiers.add(api._plugin_name)
        if getattr(target_plugin, "name", None):
            target_identifiers.add(target_plugin.name)

        if not target_identifiers:
            return

        dispatch_kwargs = {k: v for k, v in kwargs.items() if k != "app_context"}
        executed_callbacks: Set[Callable[..., Any]] = set()

        # 1. Execute registered @app_event listeners
        for name in (event_name, "*"):
            plugin_map = self._event_listeners.get(name, {})
            for ident in target_identifiers:
                listeners = plugin_map.get(ident, [])
                for callback in listeners:
                    if callback in executed_callbacks:
                        continue
                    executed_callbacks.add(callback)
                    try:
                        if inspect.iscoroutinefunction(callback):
                            await callback(*args, **dispatch_kwargs)
                        else:
                            await asyncio.to_thread(callback, *args, **dispatch_kwargs)
                    except Exception as e:
                        logger.error(
                            f"Error in plugin '{ident}' handling event '{event_name}': {e}",
                            exc_info=True,
                        )

        # 2. Lifecycle fallback (supports on_load and on_unload without requiring explicit @app_event)
        if event_name in ("on_load", "on_unload"):
            lifecycle_method = getattr(target_plugin, event_name, None)
            if (
                callable(lifecycle_method)
                and lifecycle_method not in executed_callbacks
                and not getattr(lifecycle_method, "_app_event_name", None)
                and not getattr(lifecycle_method, "_app_event_names", None)
            ):
                try:
                    if inspect.iscoroutinefunction(lifecycle_method):
                        await lifecycle_method(*args, **dispatch_kwargs)
                    else:
                        await asyncio.to_thread(
                            lifecycle_method, *args, **dispatch_kwargs
                        )
                except Exception as e:
                    logger.error(
                        f"Error in plugin '{target_plugin}' during lifecycle method '{event_name}': {e}",
                        exc_info=True,
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
        """Starts background tasks for all plugins that have methods decorated with @task_loop.

        Includes idempotency checks to prevent duplicate task loops if called multiple times.
        """
        logger.info("Starting background tasks for plugins.")
        for plugin_instance in self.plugins:
            plugin_key = (
                getattr(getattr(plugin_instance, "api", None), "_plugin_name", None)
                or plugin_instance.name
            )

            # Do not start tasks if they are already running for this plugin
            existing_tasks = self.plugin_tasks.get(plugin_key, [])
            if any(not t.done() for t in existing_tasks):
                continue

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
                                            intv * (2 ** min(consecutive_failures, 6)),
                                            300.0,
                                        )
                                    )
                                    await asyncio.sleep(sleep_time)
                                    if inspect.iscoroutinefunction(m):
                                        await m()
                                    else:
                                        await asyncio.to_thread(m)
                                    consecutive_failures = 0
                                except asyncio.CancelledError:
                                    logger.debug(
                                        f"Task loop {p_name}.{m_name} cancelled cleanly."
                                    )
                                    break
                                except Exception as e:
                                    consecutive_failures += 1
                                    logger.error(
                                        f"Error in task loop {p_name}.{m_name} (failure #{consecutive_failures}): {e}"
                                    )

                        task = asyncio.create_task(
                            run_task_loop(),
                            name=f"task_loop_{plugin_key}_{method_name}",
                        )
                        self.plugin_tasks.setdefault(plugin_key, []).append(task)
            except Exception as e:
                logger.error(
                    f"Error auto-registering tasks for plugin '{plugin_key}': {e}"
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
                            "status": status_val,
                        }
                    else:
                        existing["description"] = description
                        existing["version"] = str(version)
                        existing["author"] = author
                        existing["enabled"] = enabled_val
                        existing["status"] = status_val

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
        """Discovers, loads, initializes, and starts tasks for all enabled plugins."""
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
                        self.plugin_fastapi_routers.extend(routers)

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
                                        if resolved_dir.is_relative_to(p_dir.resolve()):
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
                                        f"Plugin '{plugin_name}' provided invalid or out-of-bounds static mount path: '{static_dir}'"
                                    )
                        self.plugin_static_mounts.extend(valid_mounts)

                if plugin_name in self.plugin_config:
                    self.plugin_config[plugin_name]["status"] = "LOADED"

            except Exception as e:
                if plugin_name in self.plugin_config:
                    self.plugin_config[plugin_name]["status"] = "ERROR"
                logger.error(
                    f"Failed to instantiate plugin '{plugin_name}': {e}", exc_info=True
                )

        logger.info(f"Loaded {len(self.plugins)} plugins.")

        # Auto-start background tasks
        await self.start_plugin_tasks()

    async def unload_plugins(self) -> None:
        """Unloads all currently loaded plugins, cleans up background tasks, and purges imported modules."""
        logger.info("--- Unloading all plugins ---")
        tasks_to_await: List[asyncio.Task[Any]] = []

        if self.plugins:
            # Unload plugins in reverse topological order (dependents before dependencies)
            for plugin_instance in reversed(list(self.plugins)):
                plugin_key = (
                    getattr(getattr(plugin_instance, "api", None), "_plugin_name", None)
                    or plugin_instance.name
                )
                try:
                    await self.dispatch_event(plugin_instance, "on_unload")
                except Exception as e:
                    logger.error(
                        f"Error during on_unload for '{plugin_key}': {e}",
                        exc_info=True,
                    )

                if plugin_key in self.plugin_tasks:
                    for task in self.plugin_tasks.pop(plugin_key):
                        task.cancel()
                        tasks_to_await.append(task)

            self.plugins.clear()

        # Cancel any remaining background tasks across all plugin keys
        for plugin_key, tasks in list(self.plugin_tasks.items()):
            for task in tasks:
                task.cancel()
                tasks_to_await.append(task)
        self.plugin_tasks.clear()

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
        logger.info("PluginManager reload complete.")

    def get_plugin_status(self, plugin_name: str) -> str:
        """Returns the runtime status of a given plugin ('LOADED', 'DISABLED', 'ERROR', or 'UNLOADED')."""
        cfg = self.plugin_config.get(plugin_name)
        is_loaded = any(
            p.name == plugin_name
            or getattr(getattr(p, "api", None), "_plugin_name", None) == plugin_name
            for p in self.plugins
        )
        if is_loaded:
            return "LOADED"
        if isinstance(cfg, dict):
            if cfg.get("status") in ("ERROR", "DISABLED", "UNLOADED"):
                return str(cfg["status"])
            if not cfg.get("enabled", False):
                return "DISABLED"
        return "UNKNOWN" if cfg is None else "UNLOADED"

    async def unload_plugin_by_name(self, plugin_name: str) -> bool:
        """Unloads a single plugin by name, stopping its tasks and unregistering its listeners."""
        target_instance = None
        for p in self.plugins:
            api = getattr(p, "api", None)
            ident = getattr(api, "_plugin_name", None) or getattr(p, "name", None)
            if p.name == plugin_name or ident == plugin_name:
                target_instance = p
                break

        if not target_instance:
            logger.warning(f"Plugin '{plugin_name}' is not currently loaded.")
            if plugin_name in self.plugin_config:
                self.plugin_config[plugin_name]["status"] = "UNLOADED"
            return False

        plugin_key = (
            getattr(getattr(target_instance, "api", None), "_plugin_name", None)
            or target_instance.name
        )

        try:
            await self.dispatch_event(target_instance, "on_unload")
        except Exception as e:
            logger.error(
                f"Error during on_unload for '{plugin_key}': {e}", exc_info=True
            )

        tasks_to_await = []
        if plugin_key in self.plugin_tasks:
            for task in self.plugin_tasks.pop(plugin_key, []):
                task.cancel()
                tasks_to_await.append(task)

        if tasks_to_await:
            await asyncio.gather(*tasks_to_await, return_exceptions=True)

        if target_instance in self.plugins:
            self.plugins.remove(target_instance)

        if callable(getattr(target_instance, "get_fastapi_routers", None)):
            try:
                routers = target_instance.get_fastapi_routers()
                if isinstance(routers, list):
                    for r in routers:
                        if r in self.plugin_fastapi_routers:
                            self.plugin_fastapi_routers.remove(r)
            except Exception as e:
                logger.error(f"Error removing routers for '{plugin_key}': {e}")

        if callable(getattr(target_instance, "get_static_mounts", None)):
            try:
                mounts = target_instance.get_static_mounts()
                if isinstance(mounts, list):
                    for m in mounts:
                        if isinstance(m, tuple) and len(m) == 3:
                            mount_tuple = (m[0], Path(m[1]).resolve(), m[2])
                            if mount_tuple in self.plugin_static_mounts:
                                self.plugin_static_mounts.remove(mount_tuple)
            except Exception as e:
                logger.error(f"Error removing static mounts for '{plugin_key}': {e}")

        for event_name, plugin_map in list(self._event_listeners.items()):
            plugin_map.pop(plugin_key, None)
            plugin_map.pop(target_instance.name, None)

        full_module_name = f"bsm_plugins.{plugin_name}"
        sys.modules.pop(full_module_name, None)

        if plugin_name in self.plugin_config:
            self.plugin_config[plugin_name]["status"] = "UNLOADED"

        logger.info(f"Plugin '{plugin_name}' unloaded successfully.")
        return True

    async def load_plugin_by_name(self, plugin_name: str) -> bool:
        """Loads and initializes a single plugin by name if discoverable."""
        for p in self.plugins:
            api = getattr(p, "api", None)
            ident = getattr(api, "_plugin_name", None) or getattr(p, "name", None)
            if p.name == plugin_name or ident == plugin_name:
                logger.info(f"Plugin '{plugin_name}' is already loaded.")
                return True

        path = self._find_plugin_path(plugin_name)
        if not path:
            logger.error(
                f"Cannot load plugin '{plugin_name}': File or directory not found."
            )
            if plugin_name in self.plugin_config:
                self.plugin_config[plugin_name]["status"] = "ERROR"
            return False

        p_class = self._get_plugin_class_from_path(path, plugin_name)
        if not p_class:
            logger.error(
                f"Cannot load plugin '{plugin_name}': No PluginBase subclass found."
            )
            if plugin_name in self.plugin_config:
                self.plugin_config[plugin_name]["status"] = "ERROR"
            return False

        try:
            plugin_logger = logging.getLogger(f"plugin.{plugin_name}")
            api_instance = create_app_api(
                plugin_name=plugin_name, app_context=self.app_context
            )

            instance = p_class(plugin_name, api_instance, plugin_logger)
            self.plugins.append(instance)

            for _, method in inspect.getmembers(instance, predicate=inspect.ismethod):
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
                    self.plugin_fastapi_routers.extend(routers)

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
                                self.plugin_static_mounts.append(
                                    (route_path, resolved_dir, mount_name)
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
                                    await asyncio.to_thread(m)
                                consecutive_failures = 0
                            except asyncio.CancelledError:
                                logger.debug(
                                    f"Task loop {p_name}.{m_name} cancelled cleanly."
                                )
                                break
                            except Exception as e:
                                consecutive_failures += 1
                                logger.error(
                                    f"Error in task loop {p_name}.{m_name} (failure #{consecutive_failures}): {e}"
                                )

                    task = asyncio.create_task(
                        run_task_loop(),
                        name=f"task_loop_{plugin_name}_{method_name}",
                    )
                    self.plugin_tasks.setdefault(plugin_name, []).append(task)

            if plugin_name in self.plugin_config:
                self.plugin_config[plugin_name]["status"] = "LOADED"
            logger.info(f"Plugin '{plugin_name}' loaded successfully.")
            return True
        except Exception as e:
            logger.error(f"Failed to load plugin '{plugin_name}': {e}", exc_info=True)
            if plugin_name in self.plugin_config:
                self.plugin_config[plugin_name]["status"] = "ERROR"
            return False

    async def reload_plugin(self, plugin_name: str) -> bool:
        """Reloads a single plugin by name."""
        logger.info(f"Reloading plugin '{plugin_name}'...")
        await self.unload_plugin_by_name(plugin_name)
        return await self.load_plugin_by_name(plugin_name)

    async def enable_plugin(
        self, plugin_name: str, load_immediately: bool = True
    ) -> bool:
        """Enables a plugin in config and optionally loads it immediately."""
        await self._synchronize_config_with_disk()
        if plugin_name not in self.plugin_config:
            logger.error(f"Cannot enable unknown plugin '{plugin_name}'.")
            return False

        self.plugin_config[plugin_name]["enabled"] = True
        await self._save_config()

        if load_immediately:
            return await self.load_plugin_by_name(plugin_name)
        self.plugin_config[plugin_name]["status"] = "DISABLED"
        return True

    async def disable_plugin(
        self, plugin_name: str, unload_immediately: bool = True
    ) -> bool:
        """Disables a plugin in config and optionally unloads it immediately."""
        await self._synchronize_config_with_disk()
        if plugin_name not in self.plugin_config:
            logger.error(f"Cannot disable unknown plugin '{plugin_name}'.")
            return False

        self.plugin_config[plugin_name]["enabled"] = False
        await self._save_config()

        if unload_immediately:
            await self.unload_plugin_by_name(plugin_name)
        self.plugin_config[plugin_name]["status"] = "DISABLED"
        return True
