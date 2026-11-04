"""Plugin capability and permission scope definitions."""

from collections.abc import Iterator, Mapping
from enum import StrEnum
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from ..context import AppContext


class PluginScope(StrEnum):
    PATH_SERVERS = "path:servers"
    PATH_BACKUPS = "path:backups"
    PATH_CONTENT = "path:content"
    PATH_DOWNLOADS = "path:downloads"
    PATH_THEMES = "path:themes"
    HEALTH_READ = "health:read"
    RUNTIME_METRICS = "runtime:metrics"
    SERVERS_READ = "servers:read"
    SERVERS_INSPECT = "servers:inspect"
    LOGS_READ = "logs:read"
    SERVERS_COMMAND = "servers:command"
    SERVERS_LIFECYCLE = "servers:lifecycle"
    SERVERS_INSTALL = "servers:install"
    PROPERTIES_READ = "properties:read"
    PROPERTIES_MANAGE = "properties:manage"
    PERMISSIONS_READ = "permissions:read"
    PERMISSIONS_MANAGE = "permissions:manage"
    ALLOWLIST_READ = "allowlist:read"
    ALLOWLIST_MANAGE = "allowlist:manage"
    BANS_READ = "bans:read"
    BANS_MANAGE = "bans:manage"
    PLAYERS_READ = "players:read"
    PLAYERS_MANAGE = "players:manage"
    WORLDS_READ = "worlds:read"
    WORLDS_MANAGE = "worlds:manage"
    WORLDS_RESET = "worlds:reset"
    ADDONS_READ = "addons:read"
    ADDONS_MANAGE = "addons:manage"
    CONTENT_READ = "content:read"
    BACKUPS_READ = "backups:read"
    BACKUPS_CREATE = "backups:create"
    BACKUPS_RESTORE = "backups:restore"
    BACKUPS_MANAGE = "backups:manage"
    BACKUPS_PRUNE = "backups:prune"
    DOWNLOADS_PRUNE = "downloads:prune"
    PLUGINS_READ = "plugins:read"
    SCHEDULER_READ = "scheduler:read"
    DIAGNOSTICS_READ = "diagnostics:read"
    WEBSOCKET_SEND = "websocket:send"


BLACKLISTED_PATH_SETTINGS: Final[frozenset[str]] = frozenset({"paths", "paths.plugins"})

GRANTABLE_PATH_SCOPES: Final[dict[str, str]] = {
    "servers": "paths.servers",
    "backups": "paths.backups",
    "content": "paths.content",
    "downloads": "paths.downloads",
    "themes": "paths.themes",
}

# Optional human-readable descriptions for known scopes (used in UI / doc generation)
SCOPE_DESCRIPTIONS: Final[dict[str, str]] = {
    PluginScope.PATH_SERVERS: "Access Bedrock server installation directories",
    PluginScope.PATH_BACKUPS: "Access backup archives and snapshot storage",
    PluginScope.PATH_CONTENT: "Access content import directories (worlds and packs)",
    PluginScope.PATH_DOWNLOADS: "Access cached server download archives",
    PluginScope.PATH_THEMES: "Access custom Web UI themes",
    PluginScope.HEALTH_READ: "Check application health and readiness",
    PluginScope.RUNTIME_METRICS: "Read application and host performance metrics",
    PluginScope.SERVERS_READ: "List servers and read their status, settings, and resource usage",
    PluginScope.SERVERS_INSPECT: "Inspect server process ownership, readiness, and runtime capabilities",
    PluginScope.LOGS_READ: "Wait for matching live Bedrock server output",
    PluginScope.SERVERS_COMMAND: "Send interactive console commands to running servers",
    PluginScope.SERVERS_LIFECYCLE: "Start, stop, and restart game servers",
    PluginScope.SERVERS_INSTALL: "Install new servers and update server software binaries",
    PluginScope.PROPERTIES_READ: "Read server.properties configuration",
    PluginScope.PROPERTIES_MANAGE: "Modify server.properties configuration",
    PluginScope.PERMISSIONS_READ: "Read Minecraft player permission levels",
    PluginScope.PERMISSIONS_MANAGE: "Modify Minecraft player operator permissions (permissions.json)",
    PluginScope.ALLOWLIST_READ: "Read a server allowlist",
    PluginScope.ALLOWLIST_MANAGE: "Add or remove players from the server allowlist",
    PluginScope.BANS_READ: "Read server player bans",
    PluginScope.BANS_MANAGE: "Add or remove server player bans",
    PluginScope.PLAYERS_READ: "Read the global known-player directory",
    PluginScope.PLAYERS_MANAGE: "Add or scan player records in the global player database",
    PluginScope.WORLDS_READ: "Read server world metadata and active world name",
    PluginScope.WORLDS_MANAGE: "Import or export Minecraft server worlds",
    PluginScope.WORLDS_RESET: "Reset and regenerate server worlds",
    PluginScope.ADDONS_READ: "Read installed server add-ons",
    PluginScope.ADDONS_MANAGE: "Enable, disable, import, or reorder server addons",
    PluginScope.CONTENT_READ: "Read shared world and add-on template libraries",
    PluginScope.BACKUPS_READ: "List, inspect, and check stored backup archives and recovery state",
    PluginScope.BACKUPS_CREATE: "Create server backups and snapshots",
    PluginScope.BACKUPS_RESTORE: "Restore server snapshots and recovery data",
    PluginScope.BACKUPS_MANAGE: "Manage, verify, drill, and pin server snapshots",
    PluginScope.BACKUPS_PRUNE: "Prune server backups using configured retention",
    PluginScope.DOWNLOADS_PRUNE: "Prune the configured server download cache",
    PluginScope.PLUGINS_READ: "Read plugin status and metadata",
    PluginScope.SCHEDULER_READ: "Read global schedules and run history",
    PluginScope.DIAGNOSTICS_READ: "Inspect runtime, event, and activity diagnostics",
    PluginScope.WEBSOCKET_SEND: "Broadcast and send messages to WebSocket clients",
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
                required_scope, f"Permission required to invoke {required_scope} APIs"
            )

    return scopes


def normalize_permissions(value: object) -> frozenset[str] | None:
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
    return frozenset(value)


def plugin_permission_declaration(plugin: object) -> frozenset[str] | None:
    """Preserve legacy None separately from an explicit empty declaration."""
    if hasattr(plugin, "_capability_permissions"):
        return normalize_permissions(getattr(plugin, "_capability_permissions"))
    return normalize_permissions(getattr(plugin, "permissions", None))


def plugin_permissions(plugin: object | None) -> frozenset[str]:
    """Return declared scopes for reporting; legacy plugins declare none."""
    return (
        (plugin_permission_declaration(plugin) or frozenset())
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
