# bedrock_server_manager/plugins/plugin_manager.py
"""Manages plugin discovery, loading, configuration, lifecycle, and event dispatch.

This module is central to the plugin architecture of the Bedrock Server Manager.
The :class:`.PluginManager` class handles all aspects of plugin interaction, including:

    - Locating plugin files in designated directories.
    - Reading and writing plugin configurations (e.g., enabled status, metadata)
      from/to a JSON file (typically ``plugins.json``).
    - Validating plugins (e.g., ensuring they subclass
      :class:`~.plugin_base.PluginBase` and have a ``version`` attribute).
    - Dynamically loading valid and enabled plugins.
    - Managing the lifecycle of plugins (e.g., calling ``on_load``, ``on_unload`` event hooks).
    - Dispatching application-wide events to all loaded plugins.
    - Facilitating custom inter-plugin event communication. Custom event names
      must follow a 'namespace:event_name' format (e.g., ``myplugin:data_updated``).
    - Providing a mechanism to reload all plugins.

"""
import os
import importlib.util
import inspect
import logging
import threading
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Type, Callable, Tuple

from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.config.const import (
    GUARD_VARIABLE,
    DEFAULT_ENABLED_PLUGINS,
    EVENT_IDENTITY_KEYS,
    _MISSING_PARAM_PLACEHOLDER,
)
from .plugin_base import PluginBase
from .api_bridge import PluginAPI

# Standard logger for this module.
logger = logging.getLogger(__name__)

# Thread-local storage for tracking the call stack of standard application events.
# This is used to prevent re-entrancy issues (infinite loops) if an event handler
# triggers an action that would cause the same event (or same event instance)
# to be dispatched again within the same thread of execution.
_event_context = threading.local()

# Thread-local storage for tracking the call stack of custom inter-plugin events.
# Similar to `_event_context`, but specifically for events sent via `send_event()`
# and handled by `trigger_custom_plugin_event()`.
_custom_event_context = threading.local()


class PluginManager:
    """Manages the discovery, loading, configuration, and lifecycle of all plugins.

    This class is the core of the plugin system. It scans for plugins,
    manages their configuration in ``plugins.json``, loads enabled plugins,
    and dispatches various events to them.
    """

    def __init__(self):
        """Initializes the PluginManager.

        Sets up plugin directories (user and default), determines the path for
        ``plugins.json``, initializes internal state for plugin configurations,
        loaded plugin instances, and custom event listeners. It also ensures
        that the configured plugin directories exist on the filesystem.
        """
        self.settings = settings
        user_plugin_dir = Path(self.settings.get("paths.plugins"))
        default_plugin_dir = Path(__file__).parent / "default"

        self.plugin_dirs: List[Path] = [user_plugin_dir, default_plugin_dir]
        logger.debug(f"Plugin directories configured: {self.plugin_dirs}")

        self.config_path: Path = Path(self.settings.config_dir) / "plugins.json"
        logger.debug(f"Plugin configuration file path: {self.config_path}")

        self.plugin_config: Dict[str, Dict[str, Any]] = {}
        self.plugins: List[PluginBase] = []
        self.custom_event_listeners: Dict[str, List[Tuple[str, Callable]]] = {}

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
        """Loads plugin configurations from the ``plugins.json`` file.

        If the file doesn't exist or is malformed, it returns an empty dictionary,
        prompting a rebuild of the configuration by methods like
        :meth:`._synchronize_config_with_disk`.

        Returns:
            Dict[str, Dict[str, Any]]: The loaded plugin configuration data,
            mapping plugin names to their configuration dictionaries.
            Returns an empty dict if loading fails or the file is not found.
        """
        if not self.config_path.exists():
            logger.debug(
                f"Plugin configuration file '{self.config_path}' not found. Returning empty config."
            )
            return {}
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)
                logger.debug(
                    f"Successfully loaded plugin configuration from '{self.config_path}'."
                )
                return config_data
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(
                f"Error decoding plugin configuration file '{self.config_path}' or its format is outdated. "
                f"Attempting to rebuild configuration. Error: {e}",
                exc_info=True,
            )
            return {}
        except Exception as e:
            logger.error(
                f"An unexpected error occurred while loading plugin configuration from '{self.config_path}': {e}",
                exc_info=True,
            )
            return {}

    def _save_config(self):
        """Saves the current in-memory plugin configuration to ``plugins.json``.

        The configuration (``self.plugin_config``) is saved in a human-readable
        JSON format, pretty-printed with indentation and sorted keys.
        """
        logger.debug(
            f"Attempting to save plugin configuration to '{self.config_path}'."
        )
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.plugin_config, f, indent=4, sort_keys=True)
            logger.info(
                f"Plugin configuration successfully saved to '{self.config_path}'."
            )
        except Exception as e:
            logger.error(
                f"Failed to save plugin configuration to '{self.config_path}': {e}",
                exc_info=True,
            )

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
            f"Searching for plugin file for '{plugin_name}' in {self.plugin_dirs}."
        )
        for directory in self.plugin_dirs:
            path = directory / f"{plugin_name}.py"
            if path.exists():
                logger.debug(f"Found plugin file for '{plugin_name}' at: {path}")
                return path
        logger.debug(
            f"Plugin file for '{plugin_name}' not found in any configured directory."
        )
        return None

    def _get_plugin_class_from_path(self, path: Path) -> Optional[Type[PluginBase]]:
        """Dynamically loads a Python module and finds the :class:`.PluginBase` subclass.

        It imports the Python module specified by `path` using :mod:`importlib.util`.
        It then inspects the module's members to find a class that is a subclass
        of :class:`.PluginBase` but is not :class:`.PluginBase` itself.

        Args:
            path (Path): The :class:`pathlib.Path` object pointing to the plugin's
                Python file.

        Returns:
            Optional[Type[:class:`.PluginBase`]]: The :class:`.PluginBase` subclass
            found in the module, or ``None`` if no such class is found or if an
            error occurs during module loading or class inspection.
        """
        plugin_name = path.stem
        logger.debug(f"Attempting to load module '{plugin_name}' from path: {path}")
        try:
            spec = importlib.util.spec_from_file_location(plugin_name, path)
            if spec is None or spec.loader is None:
                logger.error(
                    f"Could not create module spec for plugin '{plugin_name}' at {path}."
                )
                raise ImportError(f"Could not create module spec for {plugin_name}")

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            logger.debug(f"Successfully executed module '{plugin_name}' from {path}.")

            for member_name, obj in inspect.getmembers(module):
                if (
                    inspect.isclass(obj)
                    and issubclass(obj, PluginBase)
                    and obj is not PluginBase
                ):
                    logger.debug(
                        f"Found PluginBase subclass '{obj.__name__}' in module '{plugin_name}'."
                    )
                    return obj
            logger.warning(
                f"No PluginBase subclass found in module '{plugin_name}' at {path}."
            )
        except Exception as e:
            logger.error(
                f"Failed to load or inspect plugin file at '{path}' for plugin class: {e}",
                exc_info=True,
            )
        return None

    def _synchronize_config_with_disk(self):
        """Scans plugin directories, validates plugins, extracts metadata, and updates ``plugins.json``.

        This crucial method ensures the ``plugins.json`` configuration file is
        consistent with the actual plugin files found on disk. It performs the
        following steps:

            1.  Loads the existing ``plugins.json`` (via :meth:`._load_config`).
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
        all_potential_plugin_files: Dict[str, Path] = {}
        logger.debug(f"Scanning for plugin files in directories: {self.plugin_dirs}")
        for directory in self.plugin_dirs:
            if not directory.exists():
                logger.warning(
                    f"Plugin directory '{directory}' does not exist. Skipping scan for this directory."
                )
                continue
            logger.debug(f"Scanning directory: {directory}")
            for path in directory.glob("*.py"):
                if not path.name.startswith("_"):
                    plugin_name_stem = path.stem
                    if plugin_name_stem not in all_potential_plugin_files:
                        all_potential_plugin_files[plugin_name_stem] = path
                        logger.debug(
                            f"Discovered potential plugin file: '{path}' for plugin '{plugin_name_stem}'."
                        )
        logger.info(
            f"Found {len(all_potential_plugin_files)} potential plugin files across all directories."
        )

        for plugin_name, path in all_potential_plugin_files.items():
            logger.debug(
                f"Processing plugin file: '{path}' for plugin '{plugin_name}'."
            )
            plugin_class = self._get_plugin_class_from_path(path)

            if not plugin_class:
                logger.warning(
                    f"Could not find a valid PluginBase subclass in '{path}' for plugin '{plugin_name}'. "
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
                    f"Plugin class '{plugin_class.__name__}' in file '{path}' (for plugin '{plugin_name}') "
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

            valid_plugins_found_on_disk.add(plugin_name)
            version = str(version_attr).strip()
            description = inspect.getdoc(plugin_class) or "No description available."
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

    def load_plugins(self):
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
                        :class:`.api_bridge.PluginAPI` instance (for core interaction),
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

        loaded_plugin_count = 0
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
                f"Attempting to load enabled plugin: '{plugin_name}' v{plugin_version}."
            )
            path = self._find_plugin_path(plugin_name)
            if not path:
                logger.warning(
                    f"Enabled plugin '{plugin_name}' v{plugin_version} path not found on disk. Skipping load."
                )
                continue

            plugin_class = self._get_plugin_class_from_path(path)
            if plugin_class:
                try:
                    plugin_logger = logging.getLogger(f"plugin.{plugin_name}")
                    api_instance = PluginAPI(
                        plugin_name=plugin_name, plugin_manager=self
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
                    logger.debug(
                        f"Dispatching 'on_load' event to plugin '{plugin_name}'."
                    )
                    self.dispatch_event(instance, "on_load")
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
            f"Plugin loading process complete. Loaded {loaded_plugin_count} plugins."
        )

    def _is_valid_custom_event_name(self, event_name: str) -> bool:
        """Checks if a custom event name follows the 'namespace:event_name' format.

        Args:
            event_name (str): The custom event name to validate.

        Returns:
            bool: ``True`` if the `event_name` is a string and matches the
            "namespace:event_name" pattern (where both parts are non-empty),
            ``False`` otherwise.
        """
        if not isinstance(event_name, str):
            return False
        parts = event_name.split(":", 1)
        if len(parts) == 2:
            namespace, name = parts[0].strip(), parts[1].strip()
            if namespace and name:
                return True
        return False

    def register_plugin_event_listener(
        self, event_name: str, callback: Callable, listening_plugin_name: str
    ):
        """Registers a callback function from a plugin to listen for a custom event.

        Args:
            event_name (str): The name of the custom event to listen for.
                Must be in the format 'namespace:event_name' (e.g., ``myplugin:custom_signal``).
                Validation is performed by :meth:`._is_valid_custom_event_name`.
            callback (Callable): The function/method in the listening plugin
                that will be called when the specified event is triggered.
            listening_plugin_name (str): The name of the plugin registering
                the listener. Used for logging and context.
        """
        if not self._is_valid_custom_event_name(event_name):
            logger.error(
                f"Plugin '{listening_plugin_name}' attempted to register listener for custom event "
                f"'{event_name}' which does not follow the 'namespace:event_name' format. "
                f"Registration failed."
            )
            return

        if not callable(callback):
            logger.error(
                f"Plugin '{listening_plugin_name}' attempted to register a non-callable object "
                f"as a listener for custom event '{event_name}'. Registration failed."
            )
            return

        self.custom_event_listeners.setdefault(event_name, [])
        self.custom_event_listeners[event_name].append(
            (listening_plugin_name, callback)
        )
        logger.info(
            f"Plugin '{listening_plugin_name}' successfully registered a listener "
            f"for custom event '{event_name}' with callback '{callback.__name__}'."
        )
        logger.debug(
            f"Current listeners for '{event_name}': {len(self.custom_event_listeners[event_name])}"
        )

    def trigger_custom_plugin_event(
        self, event_name: str, triggering_plugin_name: str, *args, **kwargs
    ):
        """Triggers a custom event, invoking all registered listener callbacks.

        This method manages the dispatch of custom events sent by plugins (or via
        the external API trigger). It includes re-entrancy protection using
        ``_custom_event_context`` (a :class:`threading.local` stack) to prevent
        infinite loops if a listener, in turn, triggers the same event.

        The ``_triggering_plugin`` keyword argument, containing the name of the
        plugin (or "external_api_trigger") that initiated the event, is automatically
        added to the `kwargs` passed to listener callbacks.

        Args:
            event_name (str): The name of the custom event being triggered.
                Must be in the format 'namespace:event_name' (e.g., ``myplugin:data_updated``).
                Validated by :meth:`._is_valid_custom_event_name`.
            triggering_plugin_name (str): The name of the plugin that initiated
                this event.
            *args (Any): Positional arguments to pass to the listener callbacks.
            **kwargs (Any): Keyword arguments to pass to the listener callbacks.
        """
        if not self._is_valid_custom_event_name(event_name):
            logger.error(
                f"Plugin '{triggering_plugin_name}' attempted to trigger custom event "
                f"'{event_name}' which does not follow the 'namespace:event_name' format. "
                f"Event trigger aborted."
            )
            return

        if not hasattr(_custom_event_context, "stack"):
            _custom_event_context.stack = []

        if event_name in _custom_event_context.stack:
            logger.debug(
                f"Skipping recursive trigger of custom event '{event_name}' by plugin "
                f"'{triggering_plugin_name}'. Event is already in the processing stack: {_custom_event_context.stack}"
            )
            return

        _custom_event_context.stack.append(event_name)
        logger.info(
            f"Plugin '{triggering_plugin_name}' is triggering custom event '{event_name}'. "
            f"Args: {args}, Kwargs: {kwargs}. Current stack: {_custom_event_context.stack}"
        )

        try:
            listeners_for_event = self.custom_event_listeners.get(event_name, [])
            logger.debug(
                f"Found {len(listeners_for_event)} registered listeners for custom event '{event_name}'."
            )
            for listener_plugin_name, callback in listeners_for_event:
                logger.debug(
                    f"Dispatching custom event '{event_name}' (triggered by '{triggering_plugin_name}') "
                    f"to listener in plugin '{listener_plugin_name}' (callback: '{callback.__name__}')."
                )
                try:
                    callback(*args, **kwargs, _triggering_plugin=triggering_plugin_name)
                except Exception as e:
                    logger.error(
                        f"Error encountered in plugin '{listener_plugin_name}' while handling custom event "
                        f"'{event_name}' (triggered by '{triggering_plugin_name}'). Callback: '{callback.__name__}'. Error: {e}",
                        exc_info=True,
                    )
        finally:
            if hasattr(_custom_event_context, "stack") and _custom_event_context.stack:
                _custom_event_context.stack.pop()
            logger.debug(
                f"Finished processing custom event '{event_name}'. "
                f"Stack after pop: {getattr(_custom_event_context, 'stack', [])}"
            )

    def reload(self):
        """Unloads all currently active plugins and then reloads all plugins.

        This method provides a way to refresh the plugin system without restarting
        the entire application. It involves:

            1.  Dispatching the ``on_unload`` event to all currently loaded plugins
                (via :meth:`.dispatch_event`).
            2.  Clearing all registered custom event listeners from
                ``self.custom_event_listeners`` (as the plugins that registered
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

        if self.custom_event_listeners:
            logger.info(
                f"Clearing {sum(len(v) for v in self.custom_event_listeners.values())} custom plugin event listeners from {len(self.custom_event_listeners)} event types."
            )
            self.custom_event_listeners.clear()
        else:
            logger.info("No custom plugin event listeners to clear.")

        logger.info(
            "Re-running plugin discovery, synchronization, and loading process..."
        )
        self.load_plugins()

        logger.info("--- Plugin Reload Process Complete ---")

    def dispatch_event(self, target_plugin: PluginBase, event: str, *args, **kwargs):
        """Dispatches a single standard application event to a specific plugin instance.

        This method attempts to call the method corresponding to `event` on the
        `target_plugin` instance, passing ``*args`` and ``**kwargs``.
        If the `target_plugin` does not have a method for the specified `event`,
        it is logged at DEBUG level and skipped. Any exceptions raised by the
        plugin's event handler are caught and logged as errors.

        Args:
            target_plugin (:class:`.PluginBase`): The plugin instance to which the event
                should be dispatched.
            event (str): The name of the event method to call on the plugin
                (e.g., "on_load", "before_server_start").
            *args (Any): Positional arguments to pass to the event handler method.
            **kwargs (Any): Keyword arguments to pass to the event handler method.
        """
        if hasattr(target_plugin, event):
            handler_method = getattr(target_plugin, event)
            logger.debug(
                f"Dispatching standard event '{event}' to plugin '{target_plugin.name}' "
                f"(handler: '{handler_method.__name__}'). Args: {args}, Kwargs: {kwargs}"
            )
            try:
                handler_method(*args, **kwargs)
            except Exception as e:
                logger.error(
                    f"Error encountered in plugin '{target_plugin.name}' during event handler "
                    f"'{event}': {e}",
                    exc_info=True,
                )
        else:
            logger.debug(
                f"Plugin '{target_plugin.name}' does not have a handler method for event '{event}'. Skipping."
            )

    def _generate_event_key(self, event_name: str, **kwargs) -> str:
        """Generates a unique key for an event instance for re-entrancy checking.

        The key is based on the event's name and specific identifying keyword
        arguments defined in the
        :const:`~bedrock_server_manager.config.const.EVENT_IDENTITY_KEYS`
        mapping. If an event is not in this mapping or has no identity keys
        defined, the event name itself is used as the key.

        Args:
            event_name (str): The base name of the event.
            **kwargs (Any): Keyword arguments passed with the event, some of which
                might be used for forming the unique key.

        Returns:
            str: A string key representing this specific event instance.
        """
        identity_key_names = EVENT_IDENTITY_KEYS.get(event_name)

        if identity_key_names is None:
            # Event name not in EVENT_IDENTITY_KEYS, use event name as key
            return event_name

        if not identity_key_names:  # Empty tuple means event name itself is the key
            return event_name

        key_parts = [event_name]
        for key_name in identity_key_names:
            value = kwargs.get(key_name, _MISSING_PARAM_PLACEHOLDER)
            key_parts.append(str(value))

        return "|".join(key_parts)

    def trigger_event(self, event: str, *args: Any, **kwargs: Any):
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
            event (str): The name of the event to trigger (e.g., "before_server_start").
            *args (Any): Positional arguments to pass to each plugin's event handler.
            **kwargs (Any): Keyword arguments to pass to each plugin's event handler.
                       Some of these may be used by :meth:`._generate_event_key`
                       to identify the event instance.
        """
        if not hasattr(_event_context, "stack"):
            _event_context.stack = []

        current_event_key = self._generate_event_key(event, **kwargs)

        if current_event_key in _event_context.stack:
            logger.debug(
                f"Skipping recursive trigger of standard event '{event}' (key: '{current_event_key}'). "
                f"Event key is already in the processing stack: {_event_context.stack}"
            )
            return

        _event_context.stack.append(current_event_key)
        logger.debug(
            f"Dispatching standard event '{event}' (key: '{current_event_key}') to {len(self.plugins)} loaded plugins. "
            f"Args: {args}, Kwargs: {kwargs}. Current stack: {_event_context.stack}"
        )

        try:
            for plugin_instance in list(self.plugins):  # Iterate over a copy
                self.dispatch_event(plugin_instance, event, *args, **kwargs)
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
                f"Finished dispatching standard event '{event}' (key: '{current_event_key}'). "
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
            event (str): The name of the event to trigger.
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
