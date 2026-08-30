# bedrock_server_manager/plugins/plugin_base.py
"""Defines the abstract base class (ABC) for all plugins.

This module provides the :class:`.PluginBase` class, which serves as the
foundational template for all plugins within the Bedrock Server Manager
ecosystem. Plugins must inherit from this class to be recognized and loaded
by the :class:`~bedrock_server_manager.plugins.plugin_manager.PluginManager`.

By using the ``@app_event("event_name")`` decorator on their methods, plugins can subscribe to and
react to specific events triggered by the core application or other parts
of the server manager.
"""

from abc import ABC
from logging import Logger
from pathlib import Path
from typing import Any, Dict, List, cast

from .api_bridge import AppAPI


class PluginBase(ABC):
    """The abstract base class (ABC) from which all plugins must inherit.

    Plugins should subclass :class:`.PluginBase` and **must** define a class
    attribute named ``version`` (e.g., ``version = "1.0.0"``). This version string
    is used by the :class:`~bedrock_server_manager.plugins.plugin_manager.PluginManager`
    for metadata and potential compatibility checks.

    Instances of concrete plugin subclasses are provided with the following
    attributes by the :class:`~bedrock_server_manager.plugins.plugin_manager.PluginManager`
    during initialization:

    Attributes:
        name (str): The plugin's name, typically derived from its Python module
            filename (e.g., "my_plugin" for ``my_plugin.py``).
        api (:class:`~bedrock_server_manager.plugins.api_bridge.AppAPI`): An instance
            of the API bridge, providing safe access to core application functions.
        logger (:class:`logging.Logger`): A pre-configured logger instance, specific
            to this plugin. Log messages will automatically include the plugin's name.
        version (str): The plugin's own version string, copied from its class attribute.

    Plugins implement their functionality by using the ``@app_event("event_name")``
    decorator on their methods to listen for specific application events. These
    methods are called by the
    :class:`~bedrock_server_manager.plugins.plugin_manager.PluginManager`
    when corresponding application events occur.
    """

    # Class attribute: version
    # All plugins *must* override this class attribute with their specific version string.
    # Example: version = "1.2.3"
    # The PluginManager uses this for display and potentially for compatibility.
    # If not defined by a subclass, it will default to "N/A" during instantiation,
    # but the PluginManager's synchronization step enforces its presence for a plugin
    # to be considered valid and loadable.
    name: str = "N/A"  # Optional class attribute for a friendly display name.
    version: str = "N/A"  # Default placeholder, should be overridden.
    author: str = "N/A"  # Optional class attribute for plugin author information.
    description: str = ""  # Optional class attribute for plugin description.

    def __init__(self, plugin_name: str, api: AppAPI, logger: Logger):
        """Initializes the plugin instance.

        This constructor is called by the
        :class:`~bedrock_server_manager.plugins.plugin_manager.PluginManager`
        when the plugin is successfully discovered, validated, and loaded.
        It sets up the essential attributes for the plugin instance.

        Args:
            plugin_name (str): The name of the plugin, typically derived from
                its Python module filename (e.g., "my_plugin" for ``my_plugin.py``).
            api (:class:`~bedrock_server_manager.plugins.api_bridge.AppAPI`):
                An instance of the API bridge that provides a safe way for the
                plugin to call core application functions.
            logger (:class:`logging.Logger`): A pre-configured logger instance
                that is scoped to this plugin. Log messages sent via ``self.logger``
                will automatically be prefixed with the plugin's context.
        """
        # Use class property name if provided, else fallback to module name
        class_name = getattr(self.__class__, "name", "N/A")
        self.name: str = class_name if class_name != "N/A" else plugin_name
        self.api: AppAPI = api
        self.logger: Logger = logger

        # Retrieve the version from the class attribute of the concrete plugin.
        # This ensures that `self.version` reflects the version defined by the
        # actual plugin class, not the "N/A" placeholder from PluginBase.
        # The PluginManager's validation step should ensure `cls.version` exists
        # and is valid before instantiation.
        class_version = getattr(self.__class__, "version", "N/A")
        if class_version == "N/A" and self.__class__ is not PluginBase:
            # This situation should ideally be caught by PluginManager's validation,
            # but log a warning if a concrete plugin instance somehow ends up with N/A.
            self.logger.warning(
                f"Plugin '{self.name}' class is missing a 'version' attribute or it's 'N/A'. "
                "This should be defined in the plugin class."
            )
        self.version: str = class_version

        # Log the successful initialization of the plugin instance.
        # This is an INFO level log as it's a significant lifecycle event for the plugin.
        self.logger.info(
            f"Plugin '{self.name}' v{self.version} initialized and active."
        )

    def get_plugin_setting(self, key: str, default: Any = None) -> Any:
        """Retrieves a setting specific to this plugin.

        Args:
            key (str): The setting key.
            default (Any): The default value to return if the setting is not found.

        Returns:
            Any: The setting value or the default.
        """
        full_key = f"plugins.{self.name}.{key}"
        result = self.api.get_global_setting(key=full_key)
        if result and result.get("status") == "success":
            value = result.get("value")
            if value is not None:
                return value
        return default

    def set_plugin_setting(self, key: str, value: Any) -> Dict[str, Any]:
        """Saves a setting specific to this plugin.

        Args:
            key (str): The setting key.
            value (Any): The value to save.

        Returns:
            Dict[str, Any]: The result of the save operation.
        """
        full_key = f"plugins.{self.name}.{key}"
        return cast(
            Dict[str, Any], self.api.set_global_setting(key=full_key, value=value)
        )

    # --- Plugin Extension Hooks ---

    def get_fastapi_routers(self) -> List[Any]:
        """
        Called by the PluginManager after the plugin is loaded to retrieve
        any custom FastAPI routers (fastapi.APIRouter instances)
        the plugin wishes to register with the main web application.

        Plugins should override this method to return a list of APIRouter objects.

        Returns:
            List[Any]: A list of fastapi.APIRouter objects. Defaults to an empty list.
        """
        return []

    def get_static_mounts(self) -> List[tuple[str, "Path", str]]:
        """
        Called by the PluginManager after the plugin is loaded to retrieve
        configurations for mounting static file directories for this plugin.

        Each configuration should be a tuple: `(mount_path, directory_path, name)`,
        suitable for `FastAPI.mount(mount_path, StaticFiles(directory=directory_path), name=name)`.

            - `mount_path` (str): The URL path prefix for these static files (e.g., "/static/myplugin").
                                  This should be unique among plugins.
            - `directory_path` (Path): A `pathlib.Path` object pointing to the directory
                                       containing the static files for this plugin.
            - `name` (str): A unique name for this static mount (e.g., "myplugin_static").

        Example:
            from pathlib import Path
            # Assuming static files are in a 'static' subdir relative to the plugin file
            static_dir = Path(__file__).parent / "static"
            return [("/static/myplugin", static_dir, "myplugin_static")]

        Returns:
            List[tuple[str, Path, str]]: A list of tuples, each for a static directory mount.
                                        Defaults to an empty list.
        """
        return []
