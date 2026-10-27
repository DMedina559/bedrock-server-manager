# bedrock_server_manager/plugins/plugin_base.py
"""Plugin base class and extension hooks."""

from abc import ABC
from logging import Logger
from pathlib import Path
from typing import Any, ClassVar, List, cast

from pydantic import BaseModel

from ..api.models.plugins import SetPluginSettingResponse
from .api_bridge import AppAPI


class PluginBase(ABC):
    """Base class for plugins with a version, scoped API and logger.

    Declare event handlers with ``@app_event`` or register them through
    ``api.events``.
    """

    # Class attribute: version
    # All plugins *must* override this class attribute with their specific version string.
    # Example: version = "1.2.3"
    # The PluginManager uses this for display and potentially for compatibility.
    # If not defined by a subclass, it will default to "N/A" during instantiation,
    # but the PluginManager's synchronization step enforces its presence for a plugin
    # to be considered valid and loadable.
    settings_model: ClassVar[type[BaseModel] | None] = None
    global_settings_model: ClassVar[type[BaseModel] | None] = None
    server_settings_model: ClassVar[type[BaseModel] | None] = None

    name: str = "N/A"  # Optional class attribute for a friendly display name.
    version: str = "N/A"  # Default placeholder, should be overridden.
    author: str = "N/A"  # Optional class attribute for plugin author information.
    description: str = ""  # Optional class attribute for plugin description.
    dependencies: List[str] = (
        []
    )  # Optional list of required plugin names (strings) to load before this plugin.
    optional_dependencies: List[str] = (
        []
    )  # Optional list of optional plugin names (strings) to load before this plugin, if they are enabled.

    def __init__(self, plugin_name: str, api: AppAPI, logger: Logger):
        """Bind this plugin to its name, scoped API and logger."""
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
                "Plugin '%s' class is missing a 'version' attribute or it's 'N/A'. This should be defined in the plugin class.",
                self.name,
            )
        self.version: str = class_version

        # Construction precedes on_load; activation is reported by the manager.
        self.logger.debug("Plugin '%s' v%s initialized.", self.name, self.version)

    async def get_plugin_setting(
        self,
        key: str,
        default: Any = None,
        *,
        scope="plugin",
        server_name: str | None = None,
    ) -> Any:
        """Return a setting specific to this plugin.

        :param key: The setting key.
        :param default: The default value to return if the setting is not found.

        :returns: The setting value or the default.
        """
        result = await self.api.plugins.get_plugin_setting(
            request={"key": key, "scope": scope, "server_name": server_name}
        )
        if result and result.status == "success":
            value = result.value
            if value is not None:
                return value
        return default

    async def set_plugin_setting(
        self, key: str, value: Any, *, scope="plugin", server_name: str | None = None
    ) -> SetPluginSettingResponse:
        """Save a setting specific to this plugin.

        :param key: The setting key.
        :param value: The value to save.

        :returns: The validated result of the save operation.
        """
        return cast(
            SetPluginSettingResponse,
            await self.api.plugins.set_plugin_setting(
                request={
                    "key": key,
                    "value": value,
                    "scope": scope,
                    "server_name": server_name,
                }
            ),
        )

    async def get_plugin_settings(
        self, *, scope="plugin", server_name: str | None = None
    ) -> dict:
        """Read the caller's effective settings for one scope, including defaults."""
        result = await self.api.plugins.get_plugin_setting(
            request={"scope": scope, "server_name": server_name}
        )
        return cast(dict, result.value)

    async def set_plugin_settings(
        self, values: dict, *, scope="plugin", server_name: str | None = None
    ) -> SetPluginSettingResponse:
        """Atomically replace the caller's settings namespace after validation."""
        return cast(
            SetPluginSettingResponse,
            await self.api.plugins.set_plugin_setting(
                request={"value": values, "scope": scope, "server_name": server_name}
            ),
        )

    # --- Plugin Extension Hooks ---

    def get_fastapi_routers(self) -> List[Any]:
        """Called by the PluginManager after the plugin is loaded to retrieve
        any custom FastAPI routers (fastapi.APIRouter instances)
        the plugin wishes to register with the main web application.

        Plugins should override this method to return a list of APIRouter objects.

        :returns: A list of fastapi.APIRouter objects. Defaults to an empty list.
        """
        return []

    def get_static_mounts(self) -> List[tuple[str, "Path", str]]:
        """Return static mounts as ``(URL prefix, directory, name)`` tuples.

        Prefixes and names must be unique across plugins; the default is an empty
        list.
        """
        return []
