# bedrock_server_manager/plugins/api_bridge.py
"""A bridge to safely expose core application APIs to plugins."""

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
    from ..context import AppContext

logger = logging.getLogger(__name__)

# Modules allowed from bedrock_server_manager.api
ALLOWED_API_MODULES = {
    "addon",
    "allowlist",
    "application",
    "backup_restore",
    "ban",
    "install",
    "misc",
    "permissions",
    "player",
    "plugins",
    "properties",
    "server",
    "settings",
    "system",
    "websocket",
    "world",
}

# Aliases to support both singular and plural conventions (e.g., api.servers -> server)
MODULE_ALIASES = {
    "servers": "server",
    "players": "player",
    "addons": "addon",
    "bans": "ban",
    "backups": "backup_restore",
    "worlds": "world",
}

# (func, expose_to_plugins, requires_context, requires_plugin_name, origin_module)
_api_registry: Dict[str, tuple[Callable[..., Any], bool, bool, bool, str]] = {}

F = TypeVar("F", bound=Callable[..., Any])


def api_method(name: str, expose_to_plugins: bool = True) -> Callable[[F], F]:
    """Decorator to register a function with the AppAPI bridge.

    Validates that the registering function originates from one of the allowed API modules.
    """

    def decorator(func: F) -> F:
        module_name = getattr(func, "__module__", "")
        # Extract submodule name (e.g., 'bedrock_server_manager.api.server' -> 'server')
        parts = module_name.split(".")
        api_domain = parts[-1] if "api" in parts else None

        if api_domain not in ALLOWED_API_MODULES:
            logger.warning(
                f"API Registration rejected: '{module_name}.{func.__name__}' is not in the allowed "
                f"API modules list: {sorted(ALLOWED_API_MODULES)}"
            )
            return func

        if name in _api_registry:
            logger.warning(
                f"API Registration: Overwriting existing API function '{name}' "
                f"with '{module_name}.{func.__name__}'."
            )

        requires_context = False
        requires_plugin_name = False
        try:
            sig = inspect.signature(func)
            requires_context = "app_context" in sig.parameters
            requires_plugin_name = "plugin_name" in sig.parameters
        except (ValueError, TypeError):
            pass

        _api_registry[name] = (
            func,
            expose_to_plugins,
            requires_context,
            requires_plugin_name,
            api_domain,
        )
        logger.debug(
            f"API registered: '{name}' from '{module_name}' "
            f"(expose_to_plugins={expose_to_plugins}, requires_context={requires_context}, requires_plugin_name={requires_plugin_name})."
        )
        return func

    return decorator


def create_app_api(
    plugin_name: str, app_context: Optional["AppContext"], is_core: bool = False
) -> "AppAPI":
    """Factory function to create an AppAPI instance."""

    def api_dispatcher(name: str) -> Callable[..., Any]:
        if name not in _api_registry:
            logger.error(
                f"Plugin '{plugin_name}' attempted to access unregistered API: '{name}'."
            )
            raise AttributeError(
                f"The API function '{name}' has not been registered or does not exist."
            )

        (
            api_function,
            expose_to_plugins,
            requires_context,
            requires_plugin_name,
            _,
        ) = _api_registry[name]

        if not expose_to_plugins and not is_core:
            logger.error(
                f"Plugin '{plugin_name}' attempted to access internal API '{name}'."
            )
            raise AttributeError(
                f"The API function '{name}' is not exposed to plugins."
            )

        if requires_context and app_context is None:
            raise RuntimeError(
                f"API '{name}' requires app_context, but none was provided."
            )

        if inspect.iscoroutinefunction(api_function):

            @functools.wraps(api_function)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                if requires_context and "app_context" not in kwargs:
                    kwargs["app_context"] = app_context
                if requires_plugin_name:
                    try:
                        bound = inspect.signature(api_function).bind_partial(
                            *args, **kwargs
                        )
                        if "plugin_name" not in bound.arguments:
                            kwargs["plugin_name"] = plugin_name
                    except Exception:
                        if "plugin_name" not in kwargs:
                            kwargs["plugin_name"] = plugin_name
                return await api_function(*args, **kwargs)

            return async_wrapper
        else:

            @functools.wraps(api_function)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                if requires_context and "app_context" not in kwargs:
                    kwargs["app_context"] = app_context
                if requires_plugin_name:
                    try:
                        bound = inspect.signature(api_function).bind_partial(
                            *args, **kwargs
                        )
                        if "plugin_name" not in bound.arguments:
                            kwargs["plugin_name"] = plugin_name
                    except Exception:
                        if "plugin_name" not in kwargs:
                            kwargs["plugin_name"] = plugin_name
                return api_function(*args, **kwargs)

            return sync_wrapper

    def event_listener(event_name: str, callback: Callable[..., None]):
        if app_context is None or app_context.plugin_manager is None:
            raise RuntimeError("PluginManager was not found in AppContext!")
        app_context.plugin_manager.register_app_event_listener(
            event_name, callback, plugin_name
        )

    async def event_sender(event_name: str, *args: Any, **kwargs: Any):
        if app_context is None or app_context.plugin_manager is None:
            raise RuntimeError("PluginManager was not found in AppContext!")

        kwargs["_triggering_plugin"] = plugin_name
        await app_context.plugin_manager.trigger_event(event_name, *args, **kwargs)

        from bedrock_server_manager.plugins.util import broadcast_event

        await broadcast_event(app_context, event_name, kwargs)

    return AppAPI(plugin_name, api_dispatcher, event_listener, event_sender, is_core)


class CapabilityNamespace:
    """Scoped capability interface for domain operations (e.g., api.server, api.backup_restore)."""

    def __init__(self, api: "AppAPI", domain: str):
        self._api = api
        self._domain = domain

    def __getattr__(self, name: str) -> Callable[..., Any]:
        # 1. Try {domain}_{name} (e.g., server_start)
        prefixed_name = f"{self._domain}_{name}"
        try:
            return cast(Callable[..., Any], getattr(self._api, prefixed_name))
        except AttributeError:
            pass

        # 2. Try bare function name
        return cast(Callable[..., Any], getattr(self._api, name))


class AppAPI:
    """Safe, dynamic, and decoupled interface for plugins to access core APIs."""

    def __init__(
        self,
        plugin_name: str,
        api_dispatcher: Callable[[str], Callable[..., Any]],
        event_listener: Callable[[str, Callable[..., None]], None],
        event_sender: Callable[..., Awaitable[Any]],
        is_core: bool = False,
    ):
        self._plugin_name: str = plugin_name
        self._api_dispatcher = api_dispatcher
        self._event_listener = event_listener
        self._event_sender = event_sender
        self._is_core: bool = is_core
        self._namespaces: Dict[str, CapabilityNamespace] = {}

    def __getattr__(self, name: str) -> Any:
        # Security blacklist: block raw context/internal state direct access
        if name in (
            "app_context",
            "state",
            "storage",
            "db",
            "_app_context",
            "_state",
            "_storage",
        ):
            raise AttributeError(
                f"Direct access to '{name}' is forbidden via AppAPI. Use capability namespaces instead."
            )

        # Check if attribute refers to an allowed domain namespace or alias
        canonical_domain = MODULE_ALIASES.get(name, name)
        if canonical_domain in ALLOWED_API_MODULES:
            if name not in self._namespaces:
                self._namespaces[name] = CapabilityNamespace(self, canonical_domain)
            return self._namespaces[name]

        # Otherwise, resolve as a registered function name
        resolved_function = self._api_dispatcher(name)
        setattr(self, name, resolved_function)
        return resolved_function

    def list_available_apis(
        self, include_internal: Optional[bool] = None
    ) -> List[Dict[str, Any]]:
        """Returns details of all registered APIs from allowed modules."""
        if include_internal is None:
            include_internal = self._is_core

        api_details = []
        sorted_registry = sorted(
            _api_registry.items(),
            key=lambda item: (item[1][4] or "", item[0]),
        )
        for name, (func, expose_to_plugins, _, _, domain) in sorted_registry:
            if not expose_to_plugins and not include_internal:
                continue
            try:
                sig = inspect.signature(func)
                params_info = [
                    {
                        "name": p.name,
                        "type_obj": p.annotation,
                        "default": (
                            p.default
                            if p.default != inspect.Parameter.empty
                            else "REQUIRED"
                        ),
                    }
                    for p in sig.parameters.values()
                    if p.name != "app_context"
                ]
                doc = inspect.getdoc(func)
                summary = (
                    doc.strip().split("\n")[0] if doc else "No documentation available."
                )
                api_details.append(
                    {
                        "name": name,
                        "domain": domain,
                        "parameters": params_info,
                        "docstring": summary,
                        "expose_to_plugins": expose_to_plugins,
                        "is_async": inspect.iscoroutinefunction(func),
                    }
                )
            except (ValueError, TypeError):
                api_details.append(
                    {
                        "name": name,
                        "domain": domain,
                        "parameters": [],
                        "docstring": "Could not inspect signature.",
                        "expose_to_plugins": expose_to_plugins,
                        "is_async": inspect.iscoroutinefunction(func),
                    }
                )
        return api_details

    def listen_for_event(self, event_name: str, callback: Callable[..., None]):
        self._event_listener(event_name, callback)

    async def send_event(self, event_name: str, *args: Any, **kwargs: Any):
        await self._event_sender(event_name, *args, **kwargs)
