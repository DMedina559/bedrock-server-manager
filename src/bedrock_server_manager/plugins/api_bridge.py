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

from .api_contract import get_contract, validate_contract
from .api_types import API_METHODS

if TYPE_CHECKING:
    from ..context import AppContext

if TYPE_CHECKING:
    from .api_types import (
        AddonAPI,
        AllowlistAPI,
        ApplicationAPI,
        BackupRestoreAPI,
        BanAPI,
        InstallAPI,
        MiscAPI,
        PermissionsAPI,
        PlayerAPI,
        PluginsAPI,
        PropertiesAPI,
        RuntimeAPI,
        ServerAPI,
        SettingsAPI,
        SystemAPI,
        WebsocketAPI,
        WorldAPI,
    )


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
                "API Registration rejected: '%s.%s' is not in the allowed API modules list: %s",
                module_name,
                func.__name__,
                sorted(ALLOWED_API_MODULES),
            )
            return func

        if name in _api_registry:
            logger.warning(
                "API Registration: Overwriting existing API function '%s' with '%s.%s'.",
                name,
                module_name,
                func.__name__,
            )

        requires_context = False
        requires_plugin_name = False
        try:
            sig = inspect.signature(func)
            requires_context = "app_context" in sig.parameters
            requires_plugin_name = "plugin_name" in sig.parameters
        except (ValueError, TypeError):
            pass

        func = cast(F, validate_contract(func))
        _api_registry[name] = (
            func,
            expose_to_plugins,
            requires_context,
            requires_plugin_name,
            api_domain,
        )
        logger.debug(
            "API registered: '%s' from '%s' (expose_to_plugins=%s, requires_context=%s, requires_plugin_name=%s).",
            name,
            module_name,
            expose_to_plugins,
            requires_context,
            requires_plugin_name,
        )
        return func

    return decorator


def create_app_api(
    plugin_name: str, app_context: Optional["AppContext"], is_core: bool = False
) -> "AppAPI":
    """Factory function to create an AppAPI instance."""

    def runtime_dispatcher(name: str) -> Callable[..., Any]:
        from . import runtime_capabilities

        if app_context is None:
            raise RuntimeError("Runtime capabilities require application context")
        functions: dict[str, Callable[..., Any]] = {
            "run_task": runtime_capabilities.run_task,
            "server_lifecycle_manager": runtime_capabilities.server_lifecycle_manager,
            "websocket_register_data_provider": runtime_capabilities.register_data_provider,
        }
        function = functions[name]
        signature = inspect.signature(function)

        def inject(args: tuple[Any, ...], kwargs: dict[str, Any]) -> dict[str, Any]:
            bound = signature.bind_partial(*args, **kwargs)
            if {"app_context", "plugin_name"} & bound.arguments.keys():
                raise TypeError("Runtime context and plugin identity are injected")
            injected = dict(kwargs)
            injected["app_context"] = app_context
            if "plugin_name" in signature.parameters:
                injected["plugin_name"] = plugin_name
            return injected

        if inspect.iscoroutinefunction(function):

            async def async_capability(*args: Any, **kwargs: Any) -> Any:
                return await function(*args, **inject(args, kwargs))

            return async_capability

        def capability(*args: Any, **kwargs: Any) -> Any:
            return function(*args, **inject(args, kwargs))

        return capability

    def api_dispatcher(name: str) -> Callable[..., Any]:
        if name not in _api_registry:
            logger.error(
                "Plugin '%s' attempted to access unregistered API: '%s'.",
                plugin_name,
                name,
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
                "Plugin '%s' attempted to access internal API '%s'.", plugin_name, name
            )
            raise AttributeError(
                f"The API function '{name}' is not exposed to plugins."
            )

        if requires_context and app_context is None:
            raise RuntimeError(
                f"API '{name}' requires app_context, but none was provided."
            )

        def inject_runtime(
            args: tuple[Any, ...], kwargs: dict[str, Any]
        ) -> dict[str, Any]:
            bound = inspect.signature(api_function).bind_partial(*args, **kwargs)
            reserved = {"app_context", "plugin_name"} & bound.arguments.keys()
            if reserved:
                raise TypeError(
                    f"API runtime dependencies are injected: {', '.join(sorted(reserved))}"
                )
            injected = dict(kwargs)
            if requires_context:
                injected["app_context"] = app_context
            if requires_plugin_name:
                injected["plugin_name"] = plugin_name
            return injected

        public_signature = inspect.signature(api_function).replace(
            parameters=[
                parameter
                for parameter in inspect.signature(api_function).parameters.values()
                if parameter.name not in {"app_context", "plugin_name"}
            ]
        )

        if inspect.iscoroutinefunction(api_function):

            @functools.wraps(api_function)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                kwargs = inject_runtime(args, kwargs)
                return await api_function(*args, **kwargs)

            setattr(async_wrapper, "__signature__", public_signature)
            return async_wrapper
        else:

            @functools.wraps(api_function)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                kwargs = inject_runtime(args, kwargs)
                return api_function(*args, **kwargs)

            setattr(sync_wrapper, "__signature__", public_signature)
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

        from .util import _sanitize_for_json

        _sanitize_for_json(kwargs)
        kwargs["_triggering_plugin"] = plugin_name
        await app_context.plugin_manager.trigger_event(event_name, *args, **kwargs)

        from bedrock_server_manager.plugins.util import broadcast_event

        await broadcast_event(app_context, event_name, kwargs)

    return AppAPI(
        plugin_name,
        api_dispatcher,
        event_listener,
        event_sender,
        is_core,
        runtime_dispatcher,
    )


class CapabilityNamespace:
    """Scoped capability interface for domain operations (e.g., api.server, api.backup_restore)."""

    def __init__(self, api: "AppAPI", domain: str):
        self._api = api
        self._domain = domain

    def __getattr__(self, name: str) -> Callable[..., Any]:
        if self._domain == "runtime":
            names = {
                "run_task": "run_task",
                "server_lifecycle_manager": "server_lifecycle_manager",
                "register_data_provider": "websocket_register_data_provider",
            }
            if name not in names or self._api._runtime_dispatcher is None:
                raise AttributeError(f"Unknown runtime capability: {name}")
            return self._api._runtime_dispatcher(names[name])
        registered = API_METHODS.get(self._domain, {}).get(name)
        if registered is None:
            entry = _api_registry.get(name)
            if entry is None or entry[4] != self._domain:
                raise AttributeError(f"Unknown API method: {self._domain}.{name}")
            registered = name
        return self._api._api_dispatcher(registered)


class AppAPI:
    """Safe, dynamic, and decoupled interface for plugins to access core APIs."""

    @property
    def addon(self) -> "AddonAPI":
        return cast("AddonAPI", self._namespace("addon"))

    @property
    def allowlist(self) -> "AllowlistAPI":
        return cast("AllowlistAPI", self._namespace("allowlist"))

    @property
    def application(self) -> "ApplicationAPI":
        return cast("ApplicationAPI", self._namespace("application"))

    @property
    def backup_restore(self) -> "BackupRestoreAPI":
        return cast("BackupRestoreAPI", self._namespace("backup_restore"))

    @property
    def ban(self) -> "BanAPI":
        return cast("BanAPI", self._namespace("ban"))

    @property
    def install(self) -> "InstallAPI":
        return cast("InstallAPI", self._namespace("install"))

    @property
    def misc(self) -> "MiscAPI":
        return cast("MiscAPI", self._namespace("misc"))

    @property
    def permissions(self) -> "PermissionsAPI":
        return cast("PermissionsAPI", self._namespace("permissions"))

    @property
    def player(self) -> "PlayerAPI":
        return cast("PlayerAPI", self._namespace("player"))

    @property
    def plugins(self) -> "PluginsAPI":
        return cast("PluginsAPI", self._namespace("plugins"))

    @property
    def properties(self) -> "PropertiesAPI":
        return cast("PropertiesAPI", self._namespace("properties"))

    @property
    def server(self) -> "ServerAPI":
        return cast("ServerAPI", self._namespace("server"))

    @property
    def settings(self) -> "SettingsAPI":
        return cast("SettingsAPI", self._namespace("settings"))

    @property
    def system(self) -> "SystemAPI":
        return cast("SystemAPI", self._namespace("system"))

    @property
    def websocket(self) -> "WebsocketAPI":
        return cast("WebsocketAPI", self._namespace("websocket"))

    @property
    def world(self) -> "WorldAPI":
        return cast("WorldAPI", self._namespace("world"))

    @property
    def runtime(self) -> "RuntimeAPI":
        return cast("RuntimeAPI", self._namespace("runtime"))

    def _namespace(self, domain: str) -> CapabilityNamespace:
        if domain not in self._namespaces:
            self._namespaces[domain] = CapabilityNamespace(self, domain)
        return self._namespaces[domain]

    def __init__(
        self,
        plugin_name: str,
        api_dispatcher: Callable[[str], Callable[..., Any]],
        event_listener: Callable[[str, Callable[..., None]], None],
        event_sender: Callable[..., Awaitable[Any]],
        is_core: bool = False,
        runtime_dispatcher: Optional[Callable[[str], Callable[..., Any]]] = None,
    ):
        self._plugin_name: str = plugin_name
        self._api_dispatcher = api_dispatcher
        self._event_listener = event_listener
        self._event_sender = event_sender
        self._is_core: bool = is_core
        self._runtime_dispatcher = runtime_dispatcher
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

        if name in ALLOWED_API_MODULES or name == "runtime":
            if name not in self._namespaces:
                self._namespaces[name] = CapabilityNamespace(self, name)
            return self._namespaces[name]
        entry = _api_registry.get(name)
        if entry is not None and get_contract(entry[0]) is None:
            return self._api_dispatcher(name)
        raise AttributeError(f"Use a typed API namespace instead of '{name}'")

    def list_available_apis(
        self, include_internal: Optional[bool] = None
    ) -> List[Dict[str, Any]]:
        """Returns details of all registered APIs from allowed modules."""
        if include_internal is None:
            include_internal = self._is_core
        include_internal = include_internal and self._is_core

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
                contract = get_contract(func)
                from ..api.models import APIErrorResponse

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
                    if p.name not in {"app_context", "plugin_name"}
                ]
                doc = inspect.getdoc(func)
                summary = (
                    doc.strip().split("\n")[0] if doc else "No documentation available."
                )
                api_details.append(
                    {
                        "name": name,
                        "domain": domain,
                        "method": next(
                            (
                                f"{domain}.{method}"
                                for method, registered in API_METHODS.get(
                                    domain, {}
                                ).items()
                                if registered == name
                            ),
                            f"{domain}.{name}",
                        ),
                        "parameters": params_info,
                        "docstring": summary,
                        "expose_to_plugins": expose_to_plugins,
                        "is_async": inspect.iscoroutinefunction(func),
                        "contract_version": 2 if contract else 1,
                        "request_model": contract[0].__name__ if contract else None,
                        "request_schema": (
                            contract[0].model_json_schema(mode="validation")
                            if contract
                            else None
                        ),
                        "response_model": contract[1].__name__ if contract else None,
                        "response_schema": (
                            contract[1].model_json_schema(mode="serialization")
                            if contract
                            else None
                        ),
                        "error_schema": (
                            APIErrorResponse.model_json_schema(mode="serialization")
                            if contract
                            else None
                        ),
                    }
                )
            except (ValueError, TypeError):
                api_details.append(
                    {
                        "name": name,
                        "domain": domain,
                        "method": next(
                            (
                                f"{domain}.{method}"
                                for method, registered in API_METHODS.get(
                                    domain, {}
                                ).items()
                                if registered == name
                            ),
                            f"{domain}.{name}",
                        ),
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
