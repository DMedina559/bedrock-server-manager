"""Plugin capability and permission scope definitions."""

from collections.abc import Iterator, Mapping
from enum import StrEnum
from typing import TYPE_CHECKING, Final

from ..web.access_policy import CORE_DESCRIPTIONS, Permission

if TYPE_CHECKING:
    from ..context import AppContext


class PluginScope(StrEnum):
    PATH_SERVERS = "path:servers"
    PATH_BACKUPS = "path:backups"
    PATH_CONTENT = "path:content"
    PATH_DOWNLOADS = "path:downloads"
    PATH_THEMES = "path:themes"
    HEALTH_READ = str(Permission.HEALTH_READ)
    RUNTIME_METRICS = str(Permission.RUNTIME_METRICS)
    SERVERS_READ = str(Permission.SERVERS_READ)
    SERVERS_INSPECT = str(Permission.SERVERS_INSPECT)
    SERVERS_LOGS = str(Permission.SERVERS_LOGS)
    SERVERS_COMMAND = str(Permission.SERVERS_COMMAND)
    SERVERS_LIFECYCLE = str(Permission.SERVERS_LIFECYCLE)
    SERVERS_CONFIGURE = str(Permission.SERVERS_CONFIGURE)
    SERVERS_INSTALL = str(Permission.SERVERS_INSTALL)
    PROPERTIES_READ = str(Permission.PROPERTIES_READ)
    PROPERTIES_MANAGE = str(Permission.PROPERTIES_MANAGE)
    PERMISSIONS_READ = str(Permission.PERMISSIONS_READ)
    PERMISSIONS_MANAGE = str(Permission.PERMISSIONS_MANAGE)
    ALLOWLIST_READ = str(Permission.ALLOWLIST_READ)
    ALLOWLIST_MANAGE = str(Permission.ALLOWLIST_MANAGE)
    BANS_READ = str(Permission.BANS_READ)
    BANS_MANAGE = str(Permission.BANS_MANAGE)
    PLAYERS_READ = str(Permission.PLAYERS_READ)
    PLAYERS_MANAGE = str(Permission.PLAYERS_MANAGE)
    WORLDS_READ = str(Permission.WORLDS_READ)
    WORLDS_MANAGE = str(Permission.WORLDS_MANAGE)
    WORLDS_RESET = str(Permission.WORLDS_RESET)
    ADDONS_READ = str(Permission.ADDONS_READ)
    ADDONS_MANAGE = str(Permission.ADDONS_MANAGE)
    CONTENT_READ = str(Permission.CONTENT_READ)
    BACKUPS_READ = str(Permission.BACKUPS_READ)
    BACKUPS_CREATE = str(Permission.BACKUPS_CREATE)
    BACKUPS_RESTORE = str(Permission.BACKUPS_RESTORE)
    BACKUPS_MANAGE = str(Permission.BACKUPS_MANAGE)
    BACKUPS_PRUNE = str(Permission.BACKUPS_PRUNE)
    DOWNLOADS_PRUNE = str(Permission.DOWNLOADS_PRUNE)
    SETTINGS_READ = str(Permission.SETTINGS_READ)
    SETTINGS_MANAGE = str(Permission.SETTINGS_MANAGE)
    PLUGINS_READ = str(Permission.PLUGINS_READ)
    SCHEDULER_READ = str(Permission.SCHEDULER_READ)
    DIAGNOSTICS_READ = str(Permission.DIAGNOSTICS_READ)
    WEBSOCKET_SEND = "websocket:send"


BLACKLISTED_PATH_SETTINGS: Final[frozenset[str]] = frozenset({"paths", "paths.plugins"})

GRANTABLE_PATH_SCOPES: Final[dict[str, str]] = {
    "servers": "paths.servers",
    "backups": "paths.backups",
    "content": "paths.content",
    "downloads": "paths.downloads",
    "themes": "paths.themes",
}

_PLUGIN_ONLY_DESCRIPTIONS: Final[dict[str, str]] = {
    PluginScope.PATH_SERVERS: "Access Bedrock server installation directories",
    PluginScope.PATH_BACKUPS: "Access backup archives and snapshot storage",
    PluginScope.PATH_CONTENT: "Access content import directories (worlds and packs)",
    PluginScope.PATH_DOWNLOADS: "Access cached server download archives",
    PluginScope.PATH_THEMES: "Access custom Web UI themes",
    PluginScope.WEBSOCKET_SEND: "Broadcast and send messages to WebSocket clients",
}

# Human-readable descriptions for known plugin scopes (derived from canonical CORE_DESCRIPTIONS)
SCOPE_DESCRIPTIONS: Final[dict[str, str]] = {
    **_PLUGIN_ONLY_DESCRIPTIONS,
    **{
        str(scope): CORE_DESCRIPTIONS[str(scope)]
        for scope in PluginScope
        if str(scope) in CORE_DESCRIPTIONS
    },
}


def get_known_permission_scopes() -> dict[str, str]:
    """Dynamically discover all grantable capability scopes from registered APIs and path settings."""
    from .api_bridge import _api_registry

    scopes: dict[str, str] = dict(SCOPE_DESCRIPTIONS)
    for key in GRANTABLE_PATH_SCOPES:
        scope = f"path:{key}"
        scopes.setdefault(
            scope,
            SCOPE_DESCRIPTIONS.get(scope, f"Access {key} filesystem directory"),
        )

    for entry in _api_registry.values():
        required_scope = entry[5]
        if required_scope and required_scope not in scopes:
            scopes[required_scope] = SCOPE_DESCRIPTIONS.get(
                required_scope,
                CORE_DESCRIPTIONS.get(
                    required_scope,
                    f"Permission required to invoke {required_scope} APIs",
                ),
            )

    return scopes


def normalize_permissions(
    value: object, *, validate_known: bool = False
) -> frozenset[str] | None:
    """Validate plugin declarations without treating strings as collections of scopes."""
    if value is None:
        return None
    if not isinstance(value, (list, tuple, set, frozenset)):
        raise TypeError("Plugin permissions must be a collection of scope strings")
    if any(
        not isinstance(scope, str) or not scope or scope != scope.strip()
        for scope in value
    ):
        raise TypeError(
            "Plugin permissions must contain nonempty scope strings without surrounding whitespace"
        )
    normalized = frozenset(str(scope) for scope in value)
    if validate_known:
        unknown = normalized - get_known_permission_scopes().keys()
        if unknown:
            raise ValueError(
                f"Unknown plugin permission scopes: {', '.join(sorted(unknown))}"
            )
    return normalized


def plugin_permission_declaration(
    plugin: object, *, validate_known: bool = False
) -> frozenset[str] | None:
    """Preserve legacy None separately from an explicit empty declaration."""
    if hasattr(plugin, "_capability_permissions"):
        return normalize_permissions(
            getattr(plugin, "_capability_permissions"),
            validate_known=validate_known,
        )
    return normalize_permissions(
        getattr(plugin, "permissions", None),
        validate_known=validate_known,
    )


def plugin_permissions(
    plugin: object | None, *, validate_known: bool = False
) -> frozenset[str]:
    """Return declared scopes for reporting; legacy plugins declare none."""
    return (
        (
            plugin_permission_declaration(plugin, validate_known=validate_known)
            or frozenset()
        )
        if plugin is not None
        else frozenset()
    )


def plugin_has_permission(plugin: object | None, scope: str) -> bool:
    """Legacy instances keep access; explicit declarations opt into enforcement."""
    if plugin is None:
        return False
    declared = plugin_permission_declaration(plugin)
    return declared is None or scope in declared


def require_plugin_permission(
    app_context: "AppContext", plugin_name: str, scope: str
) -> None:
    plugin = app_context.plugin_manager.get_plugin(plugin_name)
    if not plugin_has_permission(plugin, scope):
        raise PermissionError(f"Plugin '{plugin_name}' requires permission '{scope}'")


class _DynamicScopesMapping(Mapping[str, str]):
    """Read-only dynamic view; every mapping operation uses the same catalog."""

    def __getitem__(self, key: str) -> str:
        return get_known_permission_scopes()[key]

    def __iter__(self) -> Iterator[str]:
        return iter(get_known_permission_scopes())

    def __len__(self) -> int:
        return len(get_known_permission_scopes())

    def copy(self) -> dict[str, str]:
        return get_known_permission_scopes()


VALID_PERMISSION_SCOPES: Final[Mapping[str, str]] = _DynamicScopesMapping()
