"""Plugin capability and permission scope definitions."""

from collections.abc import Iterator, Mapping
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from ..context import AppContext

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
    "path:servers": "Access Bedrock server installation directories",
    "path:backups": "Access backup archives and snapshot storage",
    "path:content": "Access content import directories (worlds and packs)",
    "path:downloads": "Access cached server download archives",
    "path:themes": "Access custom Web UI themes",
    "servers:inspect": "Inspect server process ownership, readiness, and runtime capabilities",
    "logs:read": "Wait for matching live Bedrock server output",
    "server:command": "Send interactive console commands to running servers",
    "server:lifecycle": "Start, stop, and restart game servers",
    "server:install": "Install new servers and update server software binaries",
    "server:properties": "Modify server.properties configuration",
    "server:permissions": "Modify Minecraft player operator permissions (permissions.json)",
    "server:allowlist": "Add or remove players from the server allowlist",
    "server:ban": "Add or remove server player bans",
    "world:manage": "Import or export Minecraft server worlds",
    "world:reset": "Reset and regenerate server worlds",
    "addon:manage": "Enable, disable, import, or reorder server addons",
    "backup:create": "Create server backups and snapshots",
    "backup:restore": "Restore server snapshots and recovery data",
    "backup:manage": "Manage, verify, drill, and pin server snapshots",
    "maintenance:backups": "Prune server backups using configured retention",
    "maintenance:downloads": "Prune the configured server download cache",
    "websocket:send": "Broadcast and send messages to WebSocket clients",
}


def get_known_permission_scopes() -> dict[str, str]:
    """Dynamically discover all grantable capability scopes from registered APIs and path settings."""
    from .api_bridge import _api_registry

    scopes: dict[str, str] = {}
    for key in GRANTABLE_PATH_SCOPES:
        scope = f"path:{key}"
        scopes[scope] = SCOPE_DESCRIPTIONS.get(
            scope, f"Access {key} filesystem directory"
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
