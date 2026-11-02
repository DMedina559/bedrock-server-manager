"""Plugin capability and permission scope definitions."""

from typing import Any, Final

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


class _DynamicScopesDict(dict[str, str]):
    """Dynamic view of permission scopes that resolves registered scopes on access."""

    def __getitem__(self, key: str) -> str:
        return get_known_permission_scopes()[key]

    def __contains__(self, key: object) -> bool:
        return key in get_known_permission_scopes()

    def __iter__(self):
        return iter(get_known_permission_scopes())

    def __len__(self) -> int:
        return len(get_known_permission_scopes())

    def items(self):
        return get_known_permission_scopes().items()

    def keys(self):
        return get_known_permission_scopes().keys()

    def values(self):
        return get_known_permission_scopes().values()

    def get(self, key: Any, default: Any = None) -> Any:  # type: ignore[override]
        return get_known_permission_scopes().get(key, default)


VALID_PERMISSION_SCOPES: Final[dict[str, str]] = _DynamicScopesDict()
