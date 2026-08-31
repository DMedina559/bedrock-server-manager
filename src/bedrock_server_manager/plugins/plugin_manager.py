# bedrock_server_manager/plugins/plugin_manager.py
"""Manages plugin discovery, loading, configuration, lifecycle, and event dispatch.

This module is central to the plugin architecture of the Bedrock Server Manager.
The :class:`.PluginManager` class handles all aspects of plugin interaction, including:

    - Locating plugin files in designated directories.
    - Reading and writing plugin configurations (e.g., enabled status, metadata)
      from/to the application database.
    - Validating plugins (e.g., ensuring they subclass
      :class:`~.plugin_base.PluginBase` and have a ``version`` attribute).
    - Dynamically loading valid and enabled plugins.
    - Managing the lifecycle of plugins (e.g., calling ``on_load``, ``on_unload`` event hooks).
    - Dispatching application-wide events to all loaded plugins.
    - Facilitating custom inter-plugin event communication. Custom event names
      must follow a 'namespace:event_name' format (e.g., ``myplugin:data_updated``).
    - Providing a mechanism to reload all plugins.

"""

import importlib.util
import inspect
import logging
import os
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple, Type

if TYPE_CHECKING:
    from ..context import AppContext

from ..config import DEFAULT_ENABLED_PLUGINS, GUARD_VARIABLE
from ..config.const import _MISSING_PARAM_PLACEHOLDER
from ..db.models import Plugin
from .api_bridge import AppAPI
from .event_trigger import _event_registry
from .plugin_base import PluginBase

# Standard logger for this module.
logger = logging.getLogger(__name__)

# Thread-local storage for tracking the call stack of standard application events.
# This is used to prevent re-entrancy issues (infinite loops) if an event handler
# triggers an action that would cause the same event (or same event instance)
# to be dispatched again within the same thread of execution.
_event_context = threading.local()

# Thread-local storage for tracking the call stack of custom inter-plugin events.
# Similar to `_event_context`, but specifically for events sent via `send_event()`
# and handled by `trigger_custom_app_event()`.
_custom_event_context = threading.local()


class PluginManager:
    """Manages the discovery, loading, aconfiguration, and lifecycle of all plugins.

    This class is the core of the plugin system. It scans for plugins,
    manages their configuration in the database, loads enabled plugins,
    and dispatches various events to them.
    """

    def __init__(self, app_context: "AppContext"):
        """
        Initializes the PluginManager.

        Sets up plugin directories (user and default), initializes internal state
        for plugin configurations, loaded plugin instances, and custom event listeners.
        It also ensures that the configured plugin directories exist on the filesystem.
        """

        self.app_context = app_context
        self.settings = app_context.settings
        user_plugin_dir = Path(self.settings.get("paths.plugins"))
        default_plugin_dir = Path(__file__).parent / "default"

        self.plugin_dirs: List[Path] = [user_plugin_dir, default_plugin_dir]
        logger.debug(f"Plugin directories configured: {self.plugin_dirs}")

        self.plugin_config: Dict[str, Dict[str, Any]] = {}
        self.plugins: List[PluginBase] = []
        self._event_listeners: Dict[str, List[Tuple[str, Callable]]] = {}
        self.plugin_fastapi_routers: List[Any] = []
        self.native_ui_render_tag = (
            "plugin-ui-native"  # Tag for Native UI rendering in FastAPI
        )
        self.plugin_static_mounts: List[tuple[str, Path, str]] = (
            []
        )  # For FastAPI app.mount()
        self.plugin_tasks: Dict[str, List[Any]] = {}

        for directory in self.plugin_dirs:
            try:
                directory.mkdir(parents=True, exist_ok=True)
                logger.debug(f"Ensured plugin directory exists: {directory}")
            except OSError as e:
                logger.error(
                    f"Failed to create plugin directory {directory}: {e}", exc_info=True
                )

        logger.info("PluginManager initialized.")

    def _load_config(self) -> Dict[str, Dict[str, Any]]:
        """Loads plugin configurations from the database.
        Returns:
            Dict[str, Dict[str, Any]]: The loaded plugin configuration data,
            mapping plugin names to their configuration dictionaries.
            Returns an empty dict if loading fails or no configuration is found.
        """
        with self.app_context.db.session_manager() as db:  # type: ignore
            plugins = db.query(Plugin).all()
            return {
                plugin.plugin_name: {
                    "enabled": plugin.enabled,
                    "version": plugin.version,
                    "author": plugin.author,
                    "description": plugin.description,
                }
                for plugin in plugins
            }

    def _save_config(self):
        """Saves the current in-memory plugin configuration to the database."""
        with self.app_context.db.session_manager() as db:
            for plugin_name, config in self.plugin_config.items():
                plugin = (
                    db.query(Plugin).filter(Plugin.plugin_name == plugin_name).first()
                )
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
            db.commit()
            logger.info("Plugin configuration successfully saved to database.")

    def _find_plugin_path(self, plugin_name: str) -> Optional[Path]:
        """Searches all configured plugin directories for a specific plugin file.

        It looks for a Python file named ``{plugin_name}.py``. The search order
        is determined by the order of directories in ``self.plugin_dirs``
        (user plugins typically take precedence over default plugins).
        The first match found is returned.

        Args:
            plugin_name (str): The name of the plugin (module name without ``.py``).

        Returns:
            Optional[Path]: The :class:`pathlib.Path` object to the plugin file
            if found, otherwise ``None``.
        """
        logger.debug(
            f"Searching for loadable path for plugin '{plugin_name}' in {self.plugin_dirs}."
        )
        for p_dir in self.plugin_dirs:  # p_dir for plugin directory
            # Check for single file plugin first: my_plugin.py
            single_file_path = p_dir / f"{plugin_name}.py"
            if single_file_path.is_file() and not single_file_path.name.startswith("_"):
                logger.debug(
                    f"Found single-file plugin for '{plugin_name}' at: {single_file_path}"
                )
                return single_file_path

            # Check for directory-based plugin: my_plugin/__init__.py
            dir_path = p_dir / plugin_name
            if (
                dir_path.is_dir()
                and not dir_path.name.startswith("_")
                and not dir_path.name.startswith(".")
            ):
                init_py_path = dir_path / "__init__.py"
                if init_py_path.is_file():
                    logger.debug(
                        f"Found directory-based plugin for '{plugin_name}' at: {init_py_path} (directory: {dir_path})"
                    )
                    return init_py_path

        logger.debug(
            f"Loadable path for plugin '{plugin_name}' not found in any configured directory."
        )
        return None

    def _get_plugin_class_from_path(
        self, path: Path, plugin_name_override: Optional[str] = None
    ) -> Optional[Type[PluginBase]]:
        """Dynamically loads a Python module and finds the :class:`.PluginBase` subclass.

        It imports the Python module specified by `path` using :mod:`importlib.util`.
        It then inspects the module's members to find a class that is a subclass
        of :class:`.PluginBase` but is not :class:`.PluginBase` itself.

        Args:
            path (Path): The :class:`pathlib.Path` object pointing to the plugin's
                Python file (e.g., `my_plugin.py` or `my_plugin_pkg/__init__.py`).
            plugin_name_override (Optional[str]): If provided, this name is used as the
                module name for importlib, which is crucial for packages.
                If None, `path.stem` is used (suitable for single file plugins).

        Returns:
            Optional[Type[:class:`.PluginBase`]]: The :class:`.PluginBase` subclass
            found in the module, or ``None`` if no such class is found or if an
            error occurs during module loading or class inspection.
        """
        # Determine the module name for importlib.
        # For a package 'my_pkg/__init__.py', path.stem would be '__init__',
        # but we need 'my_pkg' as the module name.
        # For a file 'my_file.py', path.stem is 'my_file', which is correct.
        module_name_for_spec = (
            plugin_name_override if plugin_name_override else path.stem
        )

        logger.debug(
            f"Attempting to load module '{module_name_for_spec}' from path: {path}"
        )
        try:
            spec = importlib.util.spec_from_file_location(module_name_for_spec, path)
            if spec is None or spec.loader is None:
                logger.error(
                    f"Could not create module spec for plugin '{module_name_for_spec}' at {path}."
                )
                raise ImportError(
                    f"Could not create module spec for {module_name_for_spec}"
                )

            module = importlib.util.module_from_spec(spec)
            # Important for package imports within the plugin:
            # Add the parent directory of the plugin to sys.path if it's a package
            # so that 'from . import foo' works.
            # path is either .../my_plugin.py or .../my_package/__init__.py
            import sys

            if path.name == "__init__.py":
                package_dir = (
                    path.parent.parent
                )  # Go up from __init__.py then from my_package
                if str(package_dir) not in sys.path:
                    sys.path.insert(0, str(package_dir))
                    logger.debug(
                        f"Added {package_dir} to sys.path for package plugin {module_name_for_spec}"
                    )

            # Define the package property for relative imports to work
            if path.name == "__init__.py":
                module.__package__ = module_name_for_spec
            else:
                module.__package__ = ""

            # Ensure the module is placed in sys.modules so import mechanisms can find it
            sys.modules[module_name_for_spec] = module

            spec.loader.exec_module(module)
            logger.debug(
                f"Successfully executed module '{module_name_for_spec}' from {path}."
            )

            for member_name, obj in inspect.getmembers(module):
                if (
                    inspect.isclass(obj)
                    and issubclass(obj, PluginBase)
                    and obj is not PluginBase
                ):
                    logger.debug(
                        f"Found PluginBase subclass '{obj.__name__}' in module '{module_name_for_spec}'."
                    )
                    return obj
            logger.warning(
                f"No PluginBase subclass found in module '{module_name_for_spec}' at {path}."
            )
        except Exception as e:
            logger.error(
                f"Failed to load or inspect plugin file at '{path}' (module name '{module_name_for_spec}') for plugin class: {e}",
                exc_info=True,
            )
        return None

    def _synchronize_config_with_disk(self) -> None:  # noqa: C901
        """Scans plugin directories, validates plugins, extracts metadata, and updates the database.

        This crucial method ensures the plugin configuration database is
        consistent with the actual plugin files found on disk. It performs the
        following steps:

            1.  Loads the existing plugin configuration (via :meth:`._load_config`).
            2.  Scans all directories in ``self.plugin_dirs`` for potential plugin
                files (``.py`` files not starting with an underscore).
            3.  For each potential plugin file:
                a.  Attempts to load its main plugin class using :meth:`._get_plugin_class_from_path`.
                b.  Validates the loaded plugin class:
                    i.  It must be a subclass of :class:`.PluginBase`.
                    ii. It must have a non-empty ``version`` class attribute.
                c.  If valid, extracts metadata: description (from the class's docstring)
                    and the ``version`` attribute.
                d.  Updates the in-memory ``self.plugin_config``:
                    i.  New valid plugins are added. Their initial "enabled" state
                        is determined by whether their name is in
                        :const:`~bedrock_server_manager.config.const.DEFAULT_ENABLED_PLUGINS`.
                    ii. Metadata (description, version) for existing plugin entries
                        in the config is updated if the on-disk plugin has changed.
                    iii. Handles migration of older boolean-based config entries for a
                         plugin to the newer dictionary format (containing "enabled",
                         "description", "version").
                    iv. Ensures essential keys ("enabled", "description", "version")
                         are present in each plugin's configuration entry.
            4.  Removes entries from ``self.plugin_config`` for any plugins that were
                previously in the configuration but are no longer found on disk or
                have become invalid (e.g., missing the ``version`` attribute).
            5.  If any changes were made to ``self.plugin_config`` during this process,
                the updated configuration is saved back to ``plugins.json`` using
                :meth:`._save_config`.

        This method is vital for maintaining an accurate and up-to-date registry
        of discoverable plugins and their configured states. It's typically called
        before loading plugins.
        """
        logger.info("Starting synchronization of plugin configuration with disk.")
        self.plugin_config = self._load_config()
        config_changed = False

        valid_plugins_found_on_disk = set()
        # Stores plugin_name -> path_to_load (either .py file or __init__.py)
        all_potential_plugins: Dict[str, Path] = {}
        logger.debug(f"Scanning for plugins in directories: {self.plugin_dirs}")

        for p_dir in self.plugin_dirs:  # p_dir for plugin directory
            if not p_dir.exists():
                logger.warning(
                    f"Plugin directory '{p_dir}' does not exist. Skipping scan for this directory."
                )
                continue
            logger.debug(f"Scanning directory: {p_dir}")
            for item in p_dir.iterdir():
                plugin_name = ""
                path_to_load: Optional[Path] = None

                if (
                    item.is_file()
                    and item.name.endswith(".py")
                    and not item.name.startswith("_")
                ):
                    # Single file plugin
                    plugin_name = item.stem
                    path_to_load = item
                    logger.debug(
                        f"Discovered potential single-file plugin: '{item}' for plugin name '{plugin_name}'."
                    )
                elif (
                    item.is_dir()
                    and not item.name.startswith("_")
                    and not item.name.startswith(".")
                ):
                    # Potential directory-based plugin (package)
                    init_py_path = item / "__init__.py"
                    if init_py_path.is_file():
                        plugin_name = item.name  # Directory name is the plugin name
                        path_to_load = init_py_path
                        logger.debug(
                            f"Discovered potential directory-based plugin: '{item}' (loading from '{init_py_path}') for plugin name '{plugin_name}'."
                        )

                if plugin_name and path_to_load:
                    if plugin_name in all_potential_plugins:
                        logger.warning(
                            f"Plugin name conflict: '{plugin_name}' already found at '{all_potential_plugins[plugin_name]}'. Skipping '{path_to_load}'. Check user and default plugin directories."
                        )
                    else:
                        all_potential_plugins[plugin_name] = path_to_load

        logger.info(
            f"Found {len(all_potential_plugins)} potential plugins (files/directories) across all scan paths."
        )

        for plugin_name, path_to_load in all_potential_plugins.items():
            logger.debug(
                f"Processing plugin '{plugin_name}' from path: '{path_to_load}'."
            )
            # Pass the plugin_name to _get_plugin_class_from_path for correct module naming
            plugin_class = self._get_plugin_class_from_path(
                path_to_load, plugin_name_override=plugin_name
            )

            if not plugin_class:
                logger.warning(
                    f"Could not find a valid PluginBase subclass in '{path_to_load}' for plugin '{plugin_name}'. "
                    "This file will be ignored."
                )
                if plugin_name in self.plugin_config:
                    self.plugin_config.pop(plugin_name)
                    config_changed = True
                    logger.info(
                        f"Removed invalid plugin entry '{plugin_name}' from configuration because its class "
                        "could not be loaded or is not a valid PluginBase subclass."
                    )
                continue

            version_attr = getattr(plugin_class, "version", None)
            if not version_attr or not str(version_attr).strip():
                logger.warning(
                    f"Plugin class '{plugin_class.__name__}' in file '{path_to_load}' (for plugin '{plugin_name}') "
                    "is missing a valid 'version' class attribute or the version is empty. "
                    "This plugin will be ignored and cannot be loaded."
                )
                if plugin_name in self.plugin_config:
                    self.plugin_config.pop(plugin_name)
                    config_changed = True
                    logger.info(
                        f"Removed plugin entry '{plugin_name}' from configuration due to missing or invalid 'version' attribute."
                    )
                continue

            author_attr = getattr(plugin_class, "author", None)
            valid_plugins_found_on_disk.add(plugin_name)
            version = str(version_attr).strip()
            author = str(author_attr).strip()
            description = (
                getattr(plugin_class, "description", "")
                or inspect.getdoc(plugin_class)
                or "No description available."
            )
            description = " ".join(description.strip().split())

            current_config_entry = self.plugin_config.get(plugin_name)
            needs_update_in_config = False

            if not isinstance(current_config_entry, dict):
                is_enabled_by_default = plugin_name in DEFAULT_ENABLED_PLUGINS
                is_enabled = (
                    bool(current_config_entry)
                    if isinstance(current_config_entry, bool)
                    else is_enabled_by_default
                )
                self.plugin_config[plugin_name] = {
                    "enabled": is_enabled,
                    "description": description,
                    "version": version,
                    "author": author,
                }
                config_changed = True
                needs_update_in_config = True
                if current_config_entry is None:
                    logger.info(
                        f"Discovered new valid plugin '{plugin_name}' v{version}. Added to configuration "
                        f"with enabled state: {is_enabled}."
                    )
                else:
                    logger.info(
                        f"Upgraded configuration format for plugin '{plugin_name}' v{version}. "
                        f"Set enabled state to: {is_enabled}."
                    )
            else:
                updated_entry = current_config_entry.copy()
                if "enabled" not in updated_entry:
                    updated_entry["enabled"] = plugin_name in DEFAULT_ENABLED_PLUGINS
                    needs_update_in_config = True
                    logger.debug(
                        f"Added missing 'enabled' key for plugin '{plugin_name}' in config."
                    )
                if updated_entry.get("description") != description:
                    updated_entry["description"] = description
                    needs_update_in_config = True
                    logger.debug(
                        f"Updated 'description' for plugin '{plugin_name}' in config."
                    )
                if updated_entry.get("version") != version:
                    updated_entry["version"] = version
                    needs_update_in_config = True
                    logger.debug(
                        f"Updated 'version' for plugin '{plugin_name}' to v{version} in config."
                    )
                if updated_entry.get("author") != author:
                    updated_entry["author"] = author
                    needs_update_in_config = True
                    logger.debug(
                        f"Updated 'author' for plugin '{plugin_name}' to {author} in config."
                    )
                if needs_update_in_config:
                    self.plugin_config[plugin_name] = updated_entry
                    config_changed = True
                    logger.info(
                        f"Updated metadata/config entry for plugin '{plugin_name}' (now v{version})."
                    )

        plugins_in_config_to_remove = [
            name
            for name in self.plugin_config
            if name not in valid_plugins_found_on_disk
        ]
        if plugins_in_config_to_remove:
            for plugin_name_to_remove in plugins_in_config_to_remove:
                del self.plugin_config[plugin_name_to_remove]
                config_changed = True
                logger.info(
                    f"Removed stale or invalidated plugin entry '{plugin_name_to_remove}' from configuration "
                    "as it's no longer found on disk or is invalid (e.g., missing version)."
                )

        if config_changed:
            logger.info(
                "Plugin configuration has changed during synchronization. Saving updated configuration."
            )
            self._save_config()
        else:
            logger.debug(
                "Plugin configuration synchronization complete. No changes detected."
            )

    def load_plugins(self):  # noqa: C901
        """Discovers, validates, and loads all enabled plugins.

        This method orchestrates the entire plugin loading process:

            1.  Calls :meth:`._synchronize_config_with_disk` to ensure the plugin
                configuration (``self.plugin_config``) is up-to-date with files
                on disk and that all plugin entries are valid.
            2.  Clears any previously loaded plugin instances from ``self.plugins``.
                This is important for supporting the :meth:`.reload` functionality.
            3.  Iterates through the synchronized ``self.plugin_config``:

                a.  If a plugin is marked as ``enabled`` in its configuration and has
                    a valid ``version``:

                    i.  Finds the plugin's file path using :meth:`._find_plugin_path`.

                    ii. Loads the plugin class from the file using
                        :meth:`._get_plugin_class_from_path`.

                    iii.If class loading is successful, instantiates the plugin class.
                        The instance is provided with its name, a
                        :class:`.api_bridge.AppAPI` instance (for core interaction),
                        and a dedicated :class:`logging.Logger` instance.

                    iv. Appends the new plugin instance to the ``self.plugins`` list.

                    v.  Dispatches the ``on_load`` event to the newly loaded plugin
                        instance via :meth:`.dispatch_event`.

        Errors during the loading or instantiation of individual plugins are logged,
        and the process continues with other plugins.

        """
        logger.info("Starting plugin loading process...")
        self._synchronize_config_with_disk()

        logger.info(
            f"Attempting to load plugins from configured directories: {[str(d) for d in self.plugin_dirs]}"
        )

        if self.plugins:
            logger.info(
                f"Clearing {len(self.plugins)} previously loaded plugin instances before attempting new load."
            )
            self.plugins.clear()

        # Clear any previously collected commands and routers
        self.plugin_fastapi_routers.clear()
        logger.debug("Cleared previously collected plugin FastAPI routers.")
        self.plugin_static_mounts.clear()
        logger.debug("Cleared previously collected plugin static mounts.")

        loaded_plugin_count = 0

        # 1. Collect all enabled plugins and their classes
        enabled_plugins_data: Dict[str, Type[PluginBase]] = {}
        for plugin_name, config_data in self.plugin_config.items():
            if not isinstance(config_data, dict):
                logger.error(
                    f"Plugin '{plugin_name}' has malformed config data (not a dict). Skipping. Data: {config_data}"
                )
                continue

            if not config_data.get("enabled"):
                logger.debug(
                    f"Plugin '{plugin_name}' is disabled in configuration. Skipping load."
                )
                continue

            plugin_version = config_data.get("version")
            if not plugin_version or plugin_version == "N/A":
                logger.warning(
                    f"Plugin '{plugin_name}' is marked enabled but has a missing or invalid version ('{plugin_version}') "
                    "in its configuration. Skipping load."
                )
                continue

            logger.debug(
                f"Attempting to prepare enabled plugin: '{plugin_name}' v{plugin_version}."
            )
            path = self._find_plugin_path(plugin_name)
            if not path:
                logger.warning(
                    f"Enabled plugin '{plugin_name}' v{plugin_version} path not found on disk. Skipping load."
                )
                continue

            plugin_class = self._get_plugin_class_from_path(
                path, plugin_name_override=plugin_name
            )
            if plugin_class:
                enabled_plugins_data[plugin_name] = plugin_class

        # 2. Perform Topological Sort based on dependencies
        def topological_sort(plugin_classes: Dict[str, Type[PluginBase]]) -> List[str]:
            visited = set()
            temp_mark = set()
            sorted_plugins = []

            def visit(node: str):
                if node in temp_mark:
                    logger.error(
                        f"Circular dependency detected involving plugin '{node}'. It will not be loaded."
                    )
                    return False
                if node not in visited:
                    temp_mark.add(node)
                    p_class = plugin_classes.get(node)
                    if p_class:
                        dependencies = getattr(p_class, "dependencies", [])
                        for dep in dependencies:
                            if dep not in plugin_classes:
                                logger.error(
                                    f"Plugin '{node}' requires missing or disabled dependency '{dep}'. It will not be loaded."
                                )
                                return False
                            if visit(dep) is False:
                                return False

                        optional_deps = getattr(p_class, "optional_dependencies", [])
                        for opt_dep in optional_deps:
                            if opt_dep in plugin_classes:
                                if visit(opt_dep) is False:
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

        sorted_plugin_names = topological_sort(enabled_plugins_data)

        # 3. Instantiate and load plugins in the sorted order
        for plugin_name in sorted_plugin_names:
            plugin_class = enabled_plugins_data[plugin_name]
            config_data = self.plugin_config[plugin_name]
            plugin_version = config_data.get("version")
            try:
                plugin_logger = logging.getLogger(f"plugin.{plugin_name}")
                api_instance = AppAPI(
                    plugin_name=plugin_name,
                    app_context=self.app_context,
                )
                logger.debug(
                    f"Instantiating plugin class '{plugin_class.__name__}' for '{plugin_name}'."
                )
                instance = plugin_class(plugin_name, api_instance, plugin_logger)
                self.plugins.append(instance)
                loaded_plugin_count += 1
                logger.info(
                    f"Successfully loaded and initialized plugin: '{plugin_name}' v{plugin_version}."
                )
                logger.debug(f"Dispatching 'on_load' event to plugin '{plugin_name}'.")
                self.dispatch_event(instance, "on_load")

                # Register methods decorated with @app_event
                try:
                    for method_name, method in inspect.getmembers(
                        instance, predicate=inspect.ismethod
                    ):
                        event_name = getattr(method, "_app_event_name", None)
                        if event_name:
                            logger.debug(
                                f"Auto-registering listener for event '{event_name}' on plugin '{plugin_name}'."
                            )
                            instance.api.listen_for_event(event_name, method)
                except Exception as e_event:
                    logger.error(
                        f"Error auto-registering @app_event listeners for plugin '{plugin_name}': {e_event}",
                        exc_info=True,
                    )

                # Collect FastAPI routers
                try:
                    if hasattr(instance, "get_fastapi_routers") and callable(
                        getattr(instance, "get_fastapi_routers")
                    ):
                        routers = instance.get_fastapi_routers()
                        if isinstance(routers, list) and routers:
                            self.plugin_fastapi_routers.extend(routers)
                            logger.info(
                                f"Collected {len(routers)} FastAPI router(s) from plugin '{plugin_name}'."
                            )
                            logger.warning(
                                f"Plugin '{plugin_name}' added {len(routers)} FastAPI router(s). "
                                "Ensure you trust this plugin as it can expose new web endpoints."
                            )
                        elif routers:  # Not a list or empty
                            logger.warning(
                                f"Plugin '{plugin_name}' get_fastapi_routers() did not return a list or returned an empty list."
                            )
                except Exception as e_api:
                    logger.error(
                        f"Error collecting FastAPI routers from plugin '{plugin_name}': {e_api}",
                        exc_info=True,
                    )

                # Collect static mounts
                try:
                    if hasattr(instance, "get_static_mounts") and callable(
                        getattr(instance, "get_static_mounts")
                    ):
                        static_mounts_configs = instance.get_static_mounts()
                        if (
                            isinstance(static_mounts_configs, list)
                            and static_mounts_configs
                        ):
                            valid_mounts = []
                            for mount_config in static_mounts_configs:
                                if (
                                    isinstance(mount_config, tuple)
                                    and len(mount_config) == 3
                                    and isinstance(mount_config[0], str)  # mount_path
                                    and isinstance(mount_config[1], Path)
                                    and mount_config[1].is_dir()  # dir_path
                                    and isinstance(mount_config[2], str)
                                ):  # name
                                    valid_mounts.append(mount_config)
                                else:
                                    logger.warning(
                                        f"Plugin '{plugin_name}' provided an invalid static mount configuration: {mount_config}. Expected (str, Path, str) with valid directory."
                                    )

                            self.plugin_static_mounts.extend(valid_mounts)
                            if valid_mounts:
                                logger.info(
                                    f"Collected {len(valid_mounts)} static mount(s) from plugin '{plugin_name}'."
                                )
                                logger.warning(
                                    f"Plugin '{plugin_name}' added {len(valid_mounts)} static file director(y/ies). Ensure these paths are safe and intended."
                                )
                        elif static_mounts_configs:  # Not a list or empty
                            logger.warning(
                                f"Plugin '{plugin_name}' get_static_mounts() did not return a list or returned an empty list."
                            )
                except Exception as e_static:
                    logger.error(
                        f"Error collecting static mounts from plugin '{plugin_name}': {e_static}",
                        exc_info=True,
                    )

            except Exception as e:
                logger.error(
                    f"Failed to instantiate or initialize plugin '{plugin_name}' from class '{plugin_class.__name__}': {e}",
                    exc_info=True,
                )
            else:
                logger.error(
                    f"Could not retrieve class for plugin '{plugin_name}' from path '{path}' during load phase. Skipping."
                )
        logger.info(
            f"Plugin loading process complete. Loaded {loaded_plugin_count} plugins. "
            f"{len(self.plugin_fastapi_routers)} total FastAPI router(s), "
            f"{len(self.plugin_static_mounts)} total static mounts."
        )

    async def shutdown(self):
        """Gracefully unloads all plugins asynchronously to prevent blocking."""
        import asyncio

        await asyncio.to_thread(self.unload_plugins)

    def unload_plugins(self):
        """Unloads all currently active plugins.

        This method provides a way to refresh the plugin system without restarting
        the entire application. It involves:

            1.  Dispatching the ``on_unload`` event to all currently loaded plugins
                (via :meth:`.dispatch_event`).
            2.  Clearing all registered custom event listeners from
                ``self._event_listeners`` (as the plugins that registered
                them are being unloaded).
        """
        logger.info("--- Unloading all plugins ---")

        if self.plugins:
            logger.info(f"Unloading {len(self.plugins)} currently active plugins...")
            for plugin_instance in list(self.plugins):
                logger.debug(
                    f"Dispatching 'on_unload' event to plugin '{plugin_instance.name}'."
                )
                self.dispatch_event(plugin_instance, "on_unload")

                # Cancel plugin tasks
                if plugin_instance.name in self.plugin_tasks:
                    tasks = self.plugin_tasks.pop(plugin_instance.name)
                    logger.debug(
                        f"Cancelling {len(tasks)} tasks for plugin '{plugin_instance.name}'."
                    )
                    for task in tasks:
                        task.cancel()

            logger.info(
                f"Finished dispatching 'on_unload' to {len(self.plugins)} plugins."
            )
            self.plugins.clear()
        else:
            logger.info("No plugins were active to unload.")

        if self._event_listeners:
            logger.info(
                f"Clearing {sum(len(v) for v in self._event_listeners.values())} custom plugin event listeners from {len(self._event_listeners)} event types."
            )
            self._event_listeners.clear()
        else:
            logger.info("No custom plugin event listeners to clear.")

    def get_native_ui_routes(self) -> List[Dict[str, str]]:
        """
        Collects routes from all plugin routers that are tagged for Native V2 UI rendering.

        Returns:
            List[Dict[str, str]]: A list of dictionaries, where each dictionary
                                 contains 'name', 'path', and 'type' ('native').
        """
        ui_routes = []
        for router in self.plugin_fastapi_routers:
            for route in router.routes:
                if not hasattr(route, "tags"):
                    continue

                if self.native_ui_render_tag in route.tags:
                    # Use route name or summary if available, otherwise path
                    route_name = route.name
                    if hasattr(route, "summary") and route.summary:
                        route_name = route.summary
                    elif not route_name:  # If route.name is also None or empty
                        route_name = route.path

                    ui_routes.append(
                        {"name": route_name, "path": route.path, "type": "native"}
                    )
        logger.debug(f"Collected {len(ui_routes)} Native UI rendering plugin routes.")
        return ui_routes

    def register_app_event_listener(
        self, event_name: str, callback: Callable, listening_plugin_name: str
    ):
        """Registers a callback function from a plugin to listen for an event.

        Args:
            event_name (str): The name of the event to listen for.
            callback (Callable): The function/method in the listening plugin
                that will be called when the specified event is triggered.
            listening_plugin_name (str): The name of the plugin registering
                the listener. Used for logging and context.
        """
        if not callable(callback):
            logger.error(
                f"Plugin '{listening_plugin_name}' attempted to register a non-callable object "
                f"as a listener for event '{event_name}'. Registration failed."
            )
            return

        self._event_listeners.setdefault(event_name, [])
        self._event_listeners[event_name].append((listening_plugin_name, callback))
        logger.info(
            f"Plugin '{listening_plugin_name}' successfully registered a listener "
            f"for event '{event_name}' with callback '{callback.__name__}'."
        )
        logger.debug(
            f"Current listeners for '{event_name}': {len(self._event_listeners[event_name])}"
        )

    def reload(self):
        """Unloads all currently active plugins and then reloads all plugins.

        This method provides a way to refresh the plugin system without restarting
        the entire application. It involves:

            1.  Dispatching the ``on_unload`` event to all currently loaded plugins
                (via :meth:`.dispatch_event`).
            2.  Clearing all registered custom event listeners from
                ``self._event_listeners`` (as the plugins that registered
                them are being unloaded).
            3.  Calling :meth:`.load_plugins` to re-run the discovery, synchronization,
                and loading process for all plugins based on the current disk state
                and ``plugins.json`` configuration.

        """
        logger.info("--- Starting Full Plugin Reload Process ---")

        if self.plugins:
            logger.info(f"Unloading {len(self.plugins)} currently active plugins...")
            for plugin_instance in list(self.plugins):
                logger.debug(
                    f"Dispatching 'on_unload' event to plugin '{plugin_instance.name}'."
                )
                self.dispatch_event(plugin_instance, "on_unload")
            logger.info(
                f"Finished dispatching 'on_unload' to {len(self.plugins)} plugins."
            )
        else:
            logger.info("No plugins were active to unload.")

        if self._event_listeners:
            logger.info(
                f"Clearing {sum(len(v) for v in self._event_listeners.values())} custom plugin event listeners from {len(self._event_listeners)} event types."
            )
            self._event_listeners.clear()
        else:
            logger.info("No custom plugin event listeners to clear.")

        # Also clear collected commands and routers on full reload
        self.plugin_fastapi_routers.clear()
        logger.debug("Cleared collected plugin FastAPI routers during reload.")
        self.plugin_static_mounts.clear()
        logger.debug("Cleared collected plugin static mounts during reload.")

        logger.info(
            "Re-running plugin discovery, synchronization, and loading process..."
        )
        self.load_plugins()

        logger.info("--- Plugin Reload Process Complete ---")

    def dispatch_event(
        self, target_plugin: PluginBase, event_name: str, *args, **kwargs
    ):
        """Dispatches an event to a specific plugin instance.

        Executes listeners registered via `@app_event` for this specific event
        and the wildcard `*` event. It also includes backwards compatibility for
        legacy plugins that override `before_...`, `after_...` or `on_any_event`
        methods directly.

        Args:
            target_plugin (:class:`.PluginBase`): The plugin instance to dispatch to.
            event_name (str): The name of the event.
            *args (Any): Positional arguments to pass to the event handlers.
            **kwargs (Any): Keyword arguments to pass to the event handlers.
        """
        # 1. Execute @app_event listeners for this event name and wildcard
        for event_name_to_check in (event_name, "*"):
            listeners = self._event_listeners.get(event_name_to_check, [])
            for listener_plugin_name, callback in listeners:
                if listener_plugin_name == target_plugin.name:
                    logger.debug(
                        f"Dispatching event '{event_name}' to plugin '{target_plugin.name}' "
                        f"(callback: '{callback.__name__}'). Args: {args}, Kwargs: {kwargs}"
                    )
                try:
                    if inspect.iscoroutinefunction(callback):
                        if self.app_context.loop and self.app_context.loop.is_running():
                            import asyncio

                            asyncio.run_coroutine_threadsafe(
                                callback(*args, **kwargs), self.app_context.loop
                            )
                        else:
                            logger.warning(
                                f"Event '{event_name}' on plugin '{target_plugin.name}' is an async function, but no event loop is running."
                            )
                    else:
                        callback(*args, **kwargs)
                except Exception as e:
                    logger.error(
                        f"Error in plugin '{target_plugin.name}' handling event '{event_name}': {e}",
                        exc_info=True,
                    )

        # 2. Legacy backwards compatibility: check if method exists directly on plugin
        plugin_class = type(target_plugin)
        if hasattr(target_plugin, event_name):
            class_method = getattr(plugin_class, event_name, None)
            base_method = getattr(PluginBase, event_name, None)

            if class_method is not base_method:
                handler_method = getattr(target_plugin, event_name)
                logger.debug(
                    f"Dispatching legacy event '{event_name}' to plugin '{target_plugin.name}' "
                    f"(handler: '{handler_method.__name__}')."
                )
                try:
                    if inspect.iscoroutinefunction(handler_method):
                        if self.app_context.loop and self.app_context.loop.is_running():
                            import asyncio

                            asyncio.run_coroutine_threadsafe(
                                handler_method(*args, **kwargs), self.app_context.loop
                            )
                        else:
                            logger.warning(
                                f"Legacy event '{event_name}' is async but no loop running."
                            )
                    else:
                        handler_method(*args, **kwargs)
                except Exception as e:
                    logger.error(
                        f"Error in legacy event handler '{event_name}' on '{target_plugin.name}': {e}",
                        exc_info=True,
                    )

        # Legacy backwards compatibility for on_any_event
        if hasattr(target_plugin, "on_any_event"):
            try:
                if inspect.iscoroutinefunction(target_plugin.on_any_event):
                    if self.app_context.loop and self.app_context.loop.is_running():
                        import asyncio

                        asyncio.run_coroutine_threadsafe(
                            target_plugin.on_any_event(event_name, *args, **kwargs),
                            self.app_context.loop,
                        )
                else:
                    target_plugin.on_any_event(event_name, *args, **kwargs)
            except Exception as e:
                logger.error(
                    f"Error in legacy on_any_event handler on '{target_plugin.name}': {e}",
                    exc_info=True,
                )

    async def dispatch_event_async(
        self, target_plugin: PluginBase, event_name: str, *args, **kwargs
    ):
        """Asynchronously dispatches an event to a specific plugin instance.

        Executes listeners registered via `@app_event` for this specific event
        and the wildcard `*` event. It also includes backwards compatibility for
        legacy plugins.

        Args:
            target_plugin (:class:`.PluginBase`): The plugin instance to dispatch to.
            event_name (str): The name of the event.
            *args (Any): Positional arguments to pass.
            **kwargs (Any): Keyword arguments to pass.
        """
        # 1. Execute @app_event listeners
        for event_name_to_check in (event_name, "*"):
            listeners = self._event_listeners.get(event_name_to_check, [])
            for listener_plugin_name, callback in listeners:
                if listener_plugin_name == target_plugin.name:
                    logger.debug(
                        f"Async dispatching event '{event_name}' to plugin '{target_plugin.name}' "
                        f"(callback: '{callback.__name__}')."
                    )
                try:
                    if inspect.iscoroutinefunction(callback):
                        await callback(*args, **kwargs)
                    else:
                        callback(*args, **kwargs)
                except Exception as e:
                    logger.error(
                        f"Error in plugin '{target_plugin.name}' handling async event '{event_name}': {e}",
                        exc_info=True,
                    )

        # 2. Legacy backwards compatibility
        plugin_class = type(target_plugin)
        if hasattr(target_plugin, event_name):
            class_method = getattr(plugin_class, event_name, None)
            base_method = getattr(PluginBase, event_name, None)

            if class_method is not base_method:
                handler_method = getattr(target_plugin, event_name)
                logger.debug(
                    f"Async dispatching legacy event '{event_name}' to plugin '{target_plugin.name}'."
                )
                try:
                    if inspect.iscoroutinefunction(handler_method):
                        await handler_method(*args, **kwargs)
                    else:
                        handler_method(*args, **kwargs)
                except Exception as e:
                    logger.error(
                        f"Error in legacy async event '{event_name}' on '{target_plugin.name}': {e}",
                        exc_info=True,
                    )

        if hasattr(target_plugin, "on_any_event"):
            try:
                if inspect.iscoroutinefunction(target_plugin.on_any_event):
                    await target_plugin.on_any_event(event_name, *args, **kwargs)
                else:
                    target_plugin.on_any_event(event_name, *args, **kwargs)
            except Exception as e:
                logger.error(
                    f"Error in legacy async on_any_event on '{target_plugin.name}': {e}",
                    exc_info=True,
                )

    def _generate_event_key(self, event_name: str, **kwargs) -> str:
        """Generates a unique key for an event instance for re-entrancy checking.

        The key is based on the event's name and specific identifying keyword
        arguments defined in the
        `_event_registry`
        mapping. If an event is not in this mapping or has no identity keys
        defined, the event name itself is used as the key.

        Args:
            event_name (str): The base name of the event.
            **kwargs (Any): Keyword arguments passed with the event, some of which
                might be used for forming the unique key.

        Returns:
            str: A string key representing this specific event instance.
        """
        identity_key_names = _event_registry.get(event_name)

        if identity_key_names is None:
            # Event name not in _event_registry, use event name as key
            return event_name

        if not identity_key_names:  # Empty tuple means event name itself is the key
            return event_name

        # Optimize by using string format or generator to string join
        # avoiding intermediate list append overhead.
        return "|".join(
            (
                event_name,
                *(
                    str(kwargs.get(k, _MISSING_PARAM_PLACEHOLDER))
                    for k in identity_key_names
                ),
            )
        )

    def trigger_event(self, event_name: str, *args: Any, **kwargs: Any):
        """Triggers a standard application event on all loaded plugins.

        This method iterates through all currently loaded and active plugins
        (in ``self.plugins``) and calls :meth:`.dispatch_event` for each one.
        It includes a granular re-entrancy protection mechanism using
        ``_event_context`` (a :class:`threading.local` stack) and event instance keys
        generated by :meth:`._generate_event_key` (based on
        :const:`~bedrock_server_manager.config.const.EVENT_IDENTITY_KEYS`).
        This prevents infinite loops if an event handler triggers an action that
        causes the same specific event instance to be dispatched again within the
        same call stack.

        Args:
            event_name (str): The name of the event to trigger (e.g., "before_server_start").
            *args (Any): Positional arguments to pass to each plugin's event handler.
            **kwargs (Any): Keyword arguments to pass to each plugin's event handler.
                       Some of these may be used by :meth:`._generate_event_key`
                       to identify the event instance.
        """
        if not hasattr(_event_context, "stack"):
            _event_context.stack = []

        current_event_key = self._generate_event_key(event_name, **kwargs)

        if current_event_key in _event_context.stack:
            logger.debug(
                f"Skipping recursive trigger of standard event '{event_name}' (key: '{current_event_key}'). "
                f"Event key is already in the processing stack: {_event_context.stack}"
            )
            return

        _event_context.stack.append(current_event_key)

        triggering_plugin = kwargs.get("_triggering_plugin", "core")
        logger.debug(
            f"Dispatching standard event '{event_name}' (key: '{current_event_key}', triggered by: '{triggering_plugin}') "
            f"to {len(self.plugins)} loaded plugins. Args: {args}, Kwargs: {kwargs}. Current stack: {_event_context.stack}"
        )

        try:
            for plugin_instance in list(self.plugins):  # Iterate over a copy
                self.dispatch_event(plugin_instance, event_name, *args, **kwargs)
        finally:
            if hasattr(_event_context, "stack") and _event_context.stack:
                # Ensure we pop the exact key we added, in case of complex scenarios,
                # though simple LIFO stack pop should work if events are properly nested.
                # For robustness, could remove by value, but .pop() is standard for stack.
                # If current_event_key was correctly appended, it must be the last one.
                if _event_context.stack[-1] == current_event_key:
                    _event_context.stack.pop()
                else:
                    # This case should ideally not happen with correct stack management.
                    # It might indicate an issue if events are not completing in LIFO order
                    # or if keys are not unique as expected.
                    logger.warning(
                        f"Event key '{current_event_key}' was expected at the top of the stack "
                        f"but found '{_event_context.stack[-1]}'. Stack: {_event_context.stack}. "
                        f"Attempting to remove '{current_event_key}' by value."
                    )
                    try:
                        _event_context.stack.remove(current_event_key)
                    except ValueError:
                        logger.error(
                            f"Failed to remove event key '{current_event_key}' from stack by value. "
                            f"Stack corruption may have occurred. Stack: {_event_context.stack}"
                        )

            logger.debug(
                f"Finished dispatching standard event '{event_name}' (key: '{current_event_key}'). "
                f"Stack after pop: {getattr(_event_context, 'stack', [])}"
            )

    async def trigger_event_async(self, event_name: str, *args: Any, **kwargs: Any):
        """Asynchronously triggers a standard application event on all loaded plugins.

        This method works identically to `trigger_event`, but correctly handles and awaits
        asynchronous event handlers in plugins using `dispatch_event_async`.

        Args:
            event_name (str): The name of the event to trigger.
            *args (Any): Positional arguments to pass to each plugin's event handler.
            **kwargs (Any): Keyword arguments to pass to each plugin's event handler.
        """
        if not hasattr(_event_context, "stack"):
            _event_context.stack = []

        current_event_key = self._generate_event_key(event_name, **kwargs)

        if current_event_key in _event_context.stack:
            logger.debug(
                f"Skipping recursive trigger of standard async event '{event_name}' (key: '{current_event_key}'). "
                f"Event key is already in the processing stack: {_event_context.stack}"
            )
            return

        _event_context.stack.append(current_event_key)

        triggering_plugin = kwargs.get("_triggering_plugin", "core")
        logger.debug(
            f"Dispatching standard async event '{event_name}' (key: '{current_event_key}', triggered by: '{triggering_plugin}') "
            f"to {len(self.plugins)} loaded plugins. Args: {args}, Kwargs: {kwargs}. Current stack: {_event_context.stack}"
        )

        try:
            for plugin_instance in list(self.plugins):  # Iterate over a copy
                await self.dispatch_event_async(
                    plugin_instance, event_name, *args, **kwargs
                )
        finally:
            if hasattr(_event_context, "stack") and _event_context.stack:
                if _event_context.stack[-1] == current_event_key:
                    _event_context.stack.pop()
                else:
                    logger.warning(
                        f"Event key '{current_event_key}' was expected at the top of the stack "
                        f"but found '{_event_context.stack[-1]}'. Stack: {_event_context.stack}. "
                        f"Attempting to remove '{current_event_key}' by value."
                    )
                    try:
                        _event_context.stack.remove(current_event_key)
                    except ValueError:
                        logger.error(
                            f"Failed to remove event key '{current_event_key}' from stack by value. "
                            f"Stack corruption may have occurred. Stack: {_event_context.stack}"
                        )

            logger.debug(
                f"Finished dispatching standard async event '{event_name}' (key: '{current_event_key}'). "
                f"Stack after pop: {getattr(_event_context, 'stack', [])}"
            )

    def trigger_guarded_event(self, event: str, *args, **kwargs):
        """Triggers a standard application event only if not in a guarded child process.

        This method checks for the presence of the
        :const:`~bedrock_server_manager.config.const.GUARD_VARIABLE` environment
        variable (using ``os.environ.get``). If this variable is set (indicating
        the current process might be a specially managed child process, like one
        launched for detached server operation, where certain global events should
        not be re-triggered), the event dispatch is skipped. Otherwise, it calls
        :meth:`.trigger_event`.

        Args:
            event_name (str): The name of the event to trigger.
            *args (Any): Positional arguments for the event handler.
            **kwargs (Any): Keyword arguments for the event handler.
        """
        if os.environ.get(GUARD_VARIABLE):
            logger.debug(
                f"Skipping guarded event '{event}' because GUARD_VARIABLE ('{GUARD_VARIABLE}') is set in environment."
            )
            return
        logger.debug(f"GUARD_VARIABLE not set. Proceeding to trigger event '{event}'.")
        self.trigger_event(event, *args, **kwargs)

    def start_plugin_tasks(self):
        """Starts background tasks decorated with @task_loop for all loaded plugins."""
        import asyncio

        logger.info("Starting background tasks for plugins.")
        for plugin_instance in self.plugins:
            try:
                for method_name, method in inspect.getmembers(
                    plugin_instance, predicate=inspect.ismethod
                ):
                    interval_raw = getattr(method, "_task_loop_interval", None)
                    if interval_raw is not None:
                        # Ensure interval is a number (float or int) in seconds
                        # In the updated task_loop we restricted it to int or float.
                        try:
                            interval = float(interval_raw)
                        except (ValueError, TypeError):
                            logger.error(
                                f"Invalid interval '{interval_raw}' for @task_loop on {plugin_instance.name}.{method_name}"
                            )
                            continue

                        async def run_task_loop(
                            m=method,
                            intv=interval,
                            p_name=plugin_instance.name,
                            m_name=method_name,
                        ):
                            logger.debug(
                                f"Starting task loop for {p_name}.{m_name} every {intv} seconds."
                            )
                            while True:
                                try:
                                    await asyncio.sleep(intv)
                                    if inspect.iscoroutinefunction(m):
                                        await m()
                                    else:
                                        await asyncio.to_thread(m)
                                except asyncio.CancelledError:
                                    logger.debug(
                                        f"Task loop for {p_name}.{m_name} was cancelled."
                                    )
                                    break
                                except Exception as e:
                                    logger.error(
                                        f"Error in task loop {p_name}.{m_name}: {e}",
                                        exc_info=True,
                                    )

                        task = asyncio.create_task(run_task_loop())
                        if plugin_instance.name not in self.plugin_tasks:
                            self.plugin_tasks[plugin_instance.name] = []
                        self.plugin_tasks[plugin_instance.name].append(task)
                        logger.info(
                            f"Scheduled @task_loop for {plugin_instance.name}.{method_name} (interval: {interval}s)"
                        )
            except Exception as e:
                logger.error(
                    f"Error auto-registering @task_loop for plugin '{plugin_instance.name}': {e}",
                    exc_info=True,
                )
