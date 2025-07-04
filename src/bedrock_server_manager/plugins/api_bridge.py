# bedrock_server_manager/plugins/api_bridge.py
"""A bridge to safely expose core application APIs to plugins.

This module provides a critical decoupling mechanism for the plugin system.
Instead of plugins importing API functions directly (which would create
circular dependencies and tight coupling), the core application's API modules
register their callable functions with this bridge during startup. Plugins are
then provided with an instance of the `PluginAPI` class, which grants dynamic,
safe, and version-agnostic access to these registered functions. It also
facilitates inter-plugin communication through a custom event system.
"""
import logging
from typing import Dict, Any, Callable, TYPE_CHECKING, TypeVar, List

if TYPE_CHECKING:
    # Used for type hinting to avoid circular import at runtime.
    # The PluginManager is central to plugin operations and event handling.
    from .plugin_manager import PluginManager

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
_api_registry: Dict[str, Callable[..., Any]] = {}

# Type variable for annotating the decorated function, preserving its signature.
F = TypeVar("F", bound=Callable[..., Any])


def plugin_method(name: str) -> Callable[[F], F]:
    """Decorator to register a function with the PluginAPI bridge.

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
        _api_registry[name] = func
        logger.debug(
            f"API Registration (decorator): Core API function '{func.__module__}.{func.__name__}' "
            f"successfully registered as '{name}'."
        )
        return func  # Return the original function, unmodified.

    return decorator


class PluginAPI:
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

    def __init__(self, plugin_name: str, plugin_manager: "PluginManager"):
        """Initializes the PluginAPI instance for a specific plugin.

        This constructor is called by the `PluginManager` when a plugin is
        being loaded and instantiated.

        Args:
            plugin_name (str): The name of the plugin for which this API
                instance is being created. This is used for logging and context.
            plugin_manager (PluginManager): A reference to the `PluginManager`
                instance. This is used to delegate custom event operations
                (listening and sending) to the manager.
        """
        self._plugin_name: str = plugin_name
        self._plugin_manager: "PluginManager" = plugin_manager
        logger.debug(f"PluginAPI instance created for plugin '{self._plugin_name}'.")

    def __getattr__(self, name: str) -> Callable[..., Any]:
        """Dynamically retrieves a registered core API function when accessed as an attribute.

        This magic method is the cornerstone of the API bridge's functionality.
        When a plugin executes code like `self.api.some_function_name()`, Python
        internally calls this `__getattr__` method with `name` set to
        `'some_function_name'`. This method then looks up `name` in the
        `_api_registry`.

        Args:
            name (str): The name of the attribute (API function) being accessed
                by the plugin.

        Returns:
            Callable[..., Any]: The callable API function retrieved from the
            `_api_registry` corresponding to the given `name`.

        Raises:
            AttributeError: If the function `name` has not been registered in
                the `_api_registry`, indicating the plugin is trying to access
                a non-existent or unavailable API function.
        """
        if name not in _api_registry:
            logger.error(
                f"Plugin '{self._plugin_name}' attempted to access unregistered API "
                f"function: '{name}'."
            )
            raise AttributeError(
                f"The API function '{name}' has not been registered or does not exist. "
                f"Available APIs: {list(_api_registry.keys())}"
            )
        api_function = _api_registry[name]
        logger.debug(
            f"Plugin '{self._plugin_name}' successfully accessed API function: '{name}'."
        )
        return api_function

    def list_available_apis(self) -> List[Dict[str, Any]]:
        """
        Returns a detailed list of all registered API functions, including
        their names, parameters, and documentation.

        This method can be useful for plugins that need to introspect the
        available core functionalities at runtime, or for debugging purposes
        to verify which APIs are exposed and how to call them.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries, where each dictionary
            describes a registered API function.
        """
        import inspect

        api_details = []
        logger.debug(
            f"Plugin '{self._plugin_name}' requested detailed list of available APIs."
        )

        # Iterate through the registered name and the actual function object
        for name, func in sorted(_api_registry.items()):
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

                api_details.append(
                    {"name": name, "parameters": params_info, "docstring": summary}
                )
            except (ValueError, TypeError) as e:
                # Handle cases where we can't get a signature (e.g., for some built-in C functions)
                logger.warning(f"Could not inspect signature for API '{name}': {e}")
                api_details.append(
                    {
                        "name": name,
                        "parameters": [
                            {"name": "unknown", "type": "Any", "default": "unknown"}
                        ],
                        "docstring": "Could not inspect function signature.",
                    }
                )

        return api_details

    def listen_for_event(self, event_name: str, callback: Callable[..., None]):
        """Registers a callback to be executed when a specific custom plugin event occurs.

        This method allows a plugin to subscribe to custom events that may be
        triggered by other plugins via `send_event()`. The `PluginManager`
        handles the actual registration and dispatch of these events.

        Args:
            event_name (str): The unique name of the custom event to listen for
                (e.g., "myplugin:my_custom_event"). It is a recommended practice
                to namespace event names with the originating plugin's name or
                a unique prefix to avoid collisions.
            callback (Callable[..., None]): The function or method within the
                listening plugin that should be called when the specified event
                is triggered. This callback will receive any `*args` and
                `**kwargs` passed during the `send_event` call, plus an
                additional `_triggering_plugin` keyword argument (str)
                indicating the name of the plugin that sent the event.
        """
        logger.debug(
            f"Plugin '{self._plugin_name}' is attempting to register a listener "
            f"for custom event '{event_name}' with callback '{callback.__name__}'."
        )
        # Delegate the actual registration to the PluginManager
        self._plugin_manager.register_plugin_event_listener(
            event_name, callback, self._plugin_name
        )
        # Note: The PluginManager's method will log the success/failure of registration.

    def send_event(self, event_name: str, *args: Any, **kwargs: Any):
        """Triggers a custom plugin event, notifying all registered listeners.

        This method allows a plugin to broadcast a custom event to other plugins
        that have registered a listener for it using `listen_for_event()`.
        The `PluginManager` handles the dispatch of this event to all
        subscribed callbacks.

        Args:
            event_name (str): The unique name of the custom event to trigger.
                This should match the `event_name` used by listening plugins.
            *args (Any): Positional arguments to pass to the event listeners'
                callback functions.
            **kwargs (Any): Keyword arguments to pass to the event listeners'
                callback functions.
        """
        logger.debug(
            f"Plugin '{self._plugin_name}' is attempting to send custom event "
            f"'{event_name}' with args: {args}, kwargs: {kwargs}."
        )
        # Delegate the actual event triggering to the PluginManager
        self._plugin_manager.trigger_custom_plugin_event(
            event_name, self._plugin_name, *args, **kwargs
        )
        # Note: The PluginManager's method will log the details of the event dispatch.
