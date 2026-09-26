# bedrock_server_manager/plugins/api_bridge.py
"""A bridge to safely expose core application APIs to plugins.

This module provides a critical decoupling mechanism for the plugin system.
Instead of plugins importing API functions directly (which would create
circular dependencies and tight coupling), the core application's API modules
register their callable functions with this bridge during startup. Plugins are
then provided with an instance of the `AppAPI` class, which grants dynamic,
safe, and version-agnostic access to these registered functions. It also
facilitates inter-plugin communication through a custom event system.
"""

import functools
import inspect
import logging
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Callable,
    Dict,
    List,
    Optional,
    TypeVar,
    cast,
)

if TYPE_CHECKING:
    # Used for type hinting to avoid circular import at runtime.
    # The PluginManager is central to plugin operations and event handling.
    from ..context import AppContext

# Initialize a logger for this module.
# Log messages will be prefixed with "bedrock_server_manager.plugins.api_bridge".
logger = logging.getLogger(__name__)

# _api_registry:
# This private, module-level dictionary serves as the central directory for all
# core application functions made available to plugins.
# Keys are public API names (strings) that plugins use for access.
# Values are the actual callable functions from the core application.
# This registry is populated at runtime by the `plugin_api` function,
# typically during the application's initialization phase.
_api_registry: Dict[str, tuple[Callable[..., Any], bool, bool]] = {}

# Type variable for annotating the decorated function, preserving its signature.
F = TypeVar("F", bound=Callable[..., Any])


def api_method(name: str, expose_to_plugins: bool = True) -> Callable[[F], F]:
    """Decorator to register a function with the AppAPI bridge.

    This decorator registers the decorated function in the ``_api_registry``
    under the provided ``name``. The function can then be accessed by plugins
    via ``plugin_instance.api.name()``.

    The decorated function itself is returned unmodified, so its original
    behavior is preserved.

    Example:

        ```python
        # In an API module
        from bedrock_server_manager.plugins.api_bridge import plugin_api

        @plug_api("start_my_server")
        def start_server_function(server_name: str):

            # ... implementation ...

            pass
        ```

        Plugins can then call ``self.api.start_my_server("some_server")``.

    Args:
        name (str): The public name under which to register the API method.
            This is the name plugins will use to call the function.

    Returns:
        Callable[[F], F]: A decorator that takes a function, registers it,
        and returns the original function.
    """

    def decorator(func: F) -> F:
        """Inner decorator function that performs the registration."""
        if name in _api_registry:
            logger.warning(
                f"API Registration (decorator): Overwriting existing API function '{name}' "
                f"while registering '{func.__module__}.{func.__name__}'. "
                "This may be intentional (e.g., overriding a default) or a naming conflict."
            )

        requires_context = False
        try:
            sig = inspect.signature(func)
            requires_context = "app_context" in sig.parameters
        except (ValueError, TypeError):
            pass

        _api_registry[name] = (func, expose_to_plugins, requires_context)
        logger.debug(
            f"API Registration (decorator): Core API function '{func.__module__}.{func.__name__}' "
            f"successfully registered as '{name}' (expose_to_plugins={expose_to_plugins}, requires_context={requires_context})."
        )
        return func  # Return the original function, unmodified.

    return decorator


def create_app_api(
    plugin_name: str, app_context: Optional["AppContext"], is_core: bool = False
) -> "AppAPI":
    """Factory function to create an AppAPI instance with enclosed application context.

    This approach keeps the app_context completely hidden from the plugin's introspectable
    attributes by utilizing closures for API dispatch and event handling.
    """

    def api_dispatcher(name: str) -> Callable[..., Any]:
        if name not in _api_registry:
            logger.error(
                f"Plugin '{plugin_name}' attempted to access unregistered API "
                f"function: '{name}'."
            )
            raise AttributeError(
                f"The API function '{name}' has not been registered or does not exist. "
                f"Available APIs: {[k for k, v in _api_registry.items() if v[1]]}"
            )
        api_function, expose_to_plugins, requires_context = _api_registry[name]

        if not expose_to_plugins and not is_core:
            logger.error(
                f"Plugin '{plugin_name}' attempted to access internal API '{name}'."
            )
            raise AttributeError(
                f"The API function '{name}' is not exposed to plugins."
            )

        # --- Automatic AppContext Injection ---
        if requires_context:
            if app_context is None:
                raise RuntimeError(
                    f"API '{name}' requires app_context, but it was not provided."
                )
            logger.debug(
                f"API function '{name}' expects 'app_context'. "
                "Injecting it automatically via closure."
            )
            return functools.partial(api_function, app_context=app_context)
        return api_function

    def event_listener(event_name: str, callback: Callable[..., None]):
        logger.debug(
            f"Plugin '{plugin_name}' is attempting to register a listener "
            f"for custom event '{event_name}' with callback '{callback.__name__}'."
        )
        if app_context is None or app_context.plugin_manager is None:
            raise RuntimeError("PluginManager was not found in AppContext!")
        app_context.plugin_manager.register_app_event_listener(
            event_name, callback, plugin_name
        )

    async def event_sender(event_name: str, *args: Any, **kwargs: Any):
        logger.debug(
            f"Plugin '{plugin_name}' is attempting to send event "
            f"'{event_name}' with args: {args}, kwargs: {kwargs}."
        )
        if app_context is None or app_context.plugin_manager is None:
            raise RuntimeError("PluginManager was not found in AppContext!")

        kwargs["_triggering_plugin"] = plugin_name
        await app_context.plugin_manager.trigger_event(event_name, *args, **kwargs)

        from bedrock_server_manager.plugins.util import broadcast_event

        await broadcast_event(app_context, event_name, kwargs)

    return AppAPI(plugin_name, api_dispatcher, event_listener, event_sender, is_core)


class CapabilityNamespace:
    """Scoped capability interface for domain operations (e.g., api.servers, api.settings)."""

    def __init__(self, api: "AppAPI", domain: str):
        self._api = api
        self._domain = domain

    def __getattr__(self, name: str) -> Callable[..., Any]:
        return cast(Callable[..., Any], getattr(self._api, name))


class AppAPI:
    """Provides a safe, dynamic, and decoupled interface for plugins to access core APIs.

    An instance of this class is passed to each plugin upon its initialization
    by the `PluginManager`. Plugins use this instance (typically `self.api`)
    to call registered core functions (e.g., `self.api.start_server(...)`)
    without needing to import them directly, thus avoiding circular dependencies
    and promoting a cleaner architecture.

    This class also provides methods for plugins to interact with the custom
    plugin event system, allowing them to listen for and send events to
    other plugins.
    """

    def __init__(
        self,
        plugin_name: str,
        api_dispatcher: Callable[[str], Callable[..., Any]],
        event_listener: Callable[[str, Callable[..., None]], None],
        event_sender: Callable[..., Awaitable[Any]],
        is_core: bool = False,
    ):
        """Initializes the AppAPI instance for a specific plugin.

        This constructor is called by the `create_app_api` factory.

        Args:
            plugin_name (str): The name of the plugin for which this API
                instance is being created. This is used for logging and context.
            api_dispatcher (Callable): A closure that resolves APIs and injects context.
            event_listener (Callable): A closure to handle event listening.
            event_sender (Callable): A closure to handle event dispatching.
            is_core (bool): If True, bypasses internal plugin API access checks.
        """
        self._plugin_name: str = plugin_name
        self._api_dispatcher = api_dispatcher
        self._event_listener = event_listener
        self._event_sender = event_sender
        self._is_core: bool = is_core

        self._servers = CapabilityNamespace(self, "servers")
        self._settings = CapabilityNamespace(self, "settings")
        self._players = CapabilityNamespace(self, "players")
        self._plugins = CapabilityNamespace(self, "plugins")
        self._tasks = CapabilityNamespace(self, "tasks")

        logger.debug(
            f"AppAPI instance created for plugin '{self._plugin_name}' (is_core={is_core})."
        )

    @property
    def servers(self) -> CapabilityNamespace:
        """Scoped capability interface for server operations."""
        return self._servers

    @property
    def settings(self) -> CapabilityNamespace:
        """Scoped capability interface for settings operations."""
        return self._settings

    @property
    def players(self) -> CapabilityNamespace:
        """Scoped capability interface for player operations."""
        return self._players

    @property
    def plugins(self) -> CapabilityNamespace:
        """Scoped capability interface for plugin operations."""
        return self._plugins

    @property
    def tasks(self) -> CapabilityNamespace:
        """Scoped capability interface for task operations."""
        return self._tasks

    def __getattr__(self, name: str) -> Callable[..., Any]:
        """Dynamically retrieves a registered core API function when accessed as an attribute.

        Args:
            name (str): The name of the attribute (API function) being accessed
                by the plugin.

        Returns:
            Callable[..., Any]: The callable API function.
        """
        resolved_function = self._api_dispatcher(name)
        logger.debug(
            f"Plugin '{self._plugin_name}' successfully accessed API function: '{name}'."
        )
        setattr(self, name, resolved_function)
        return resolved_function

    def list_available_apis(
        self, include_internal: Optional[bool] = None
    ) -> List[Dict[str, Any]]:
        """
        Returns a detailed list of all registered API functions, including
        their names, parameters, and documentation.

        This method can be useful for plugins that need to introspect the
        available core functionalities at runtime, or for debugging purposes
        to verify which APIs are exposed and how to call them.

        Args:
            include_internal (Optional[bool]): If True, includes APIs not exposed to plugins.
                                               Defaults to True if is_core is True, otherwise False.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries, where each dictionary
            describes a registered API function.
        """
        import inspect

        if include_internal is None:
            include_internal = self._is_core

        api_details = []
        logger.debug(
            f"Plugin '{self._plugin_name}' requested detailed list of available APIs (include_internal={include_internal})."
        )

        # Iterate through the registered name and the actual function object
        for name, (func, expose_to_plugins, _) in sorted(_api_registry.items()):
            if not expose_to_plugins and not include_internal:
                continue
            try:
                # Use inspect.signature to get the function's signature
                sig = inspect.signature(func)
                params_info = []

                for param in sig.parameters.values():
                    param_info = {
                        "name": param.name,
                        "type_obj": param.annotation,
                        # Check if there's a default value
                        "default": (
                            param.default
                            if param.default != inspect.Parameter.empty
                            else "REQUIRED"
                        ),
                    }
                    params_info.append(param_info)

                # Get the first line of the docstring as a summary
                doc = inspect.getdoc(func)
                summary = (
                    doc.strip().split("\n")[0] if doc else "No documentation available."
                )
                is_async = inspect.iscoroutinefunction(func)

                api_details.append(
                    {
                        "name": name,
                        "parameters": params_info,
                        "docstring": summary,
                        "expose_to_plugins": expose_to_plugins,
                        "is_async": is_async,
                    }
                )
            except (ValueError, TypeError) as e:
                # Handle cases where we can't get a signature (e.g., for some built-in C functions)
                logger.warning(f"Could not inspect signature for API '{name}': {e}")
                is_async = inspect.iscoroutinefunction(func)
                api_details.append(
                    {
                        "name": name,
                        "parameters": [
                            {"name": "unknown", "type": "Any", "default": "unknown"}
                        ],
                        "docstring": "Could not inspect function signature.",
                        "expose_to_plugins": expose_to_plugins,
                        "is_async": is_async,
                    }
                )

        return api_details

    def listen_for_event(self, event_name: str, callback: Callable[..., None]):
        """Registers a callback to be executed when a specific custom plugin event occurs."""
        self._event_listener(event_name, callback)

    async def send_event(self, event_name: str, *args: Any, **kwargs: Any):
        """Triggers an event, notifying all registered listeners and broadcasting to WebSockets."""
        await self._event_sender(event_name, *args, **kwargs)
