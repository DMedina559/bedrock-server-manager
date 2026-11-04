"""Role-derived HTTP capabilities. These are endpoint scopes, not token grants."""

import re
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Callable, cast
from uuid import uuid4
from weakref import WeakSet


class Permission(StrEnum):
    HEALTH_READ = "health:read"
    TOKENS_MANAGE = "tokens:manage"
    SESSIONS_MANAGE = "sessions:manage"
    SESSIONS_ADMIN = "sessions:admin"
    ACCESS_MANAGE = "access:manage"
    ACCOUNT_READ = "account:read"
    ACCOUNT_MANAGE = "account:manage"
    SERVERS_READ = "servers:read"
    TASKS_READ = "tasks:read"
    PLUGINS_PAGES = "plugins:pages"
    RUNTIME_METRICS = "runtime:metrics"
    SERVERS_INSPECT = "servers:inspect"
    SERVERS_LIFECYCLE = "servers:lifecycle"
    SERVERS_COMMAND = "servers:command"
    PROPERTIES_READ = "properties:read"
    PROPERTIES_MANAGE = "properties:manage"
    PLAYERS_READ = "players:read"
    PLAYERS_MANAGE = "players:manage"
    ALLOWLIST_READ = "allowlist:read"
    ALLOWLIST_MANAGE = "allowlist:manage"
    PERMISSIONS_READ = "permissions:read"
    PERMISSIONS_MANAGE = "permissions:manage"
    USERS_READ = "users:read"
    LOGS_READ = "logs:read"
    BACKUPS_READ = "backups:read"
    BACKUPS_CREATE = "backups:create"
    BACKUPS_RESTORE = "backups:restore"
    BACKUPS_MANAGE = "backups:manage"
    BACKUPS_PRUNE = "backups:prune"
    CONTENT_READ = "content:read"
    ADDONS_READ = "addons:read"
    DOWNLOADS_READ = "downloads:read"
    SERVERS_CONFIGURE = "servers:configure"
    SERVERS_INSTALL = "servers:install"
    SERVERS_DELETE = "servers:delete"
    USERS_MANAGE = "users:manage"
    SETTINGS_READ = "settings:read"
    SETTINGS_MANAGE = "settings:manage"
    LOGS_READ_APPLICATION = "logs:read_application"
    DIAGNOSTICS_READ = "diagnostics:read"
    AUDIT_READ = "audit:read"
    PLUGINS_READ = "plugins:read"
    PLUGINS_MANAGE = "plugins:manage"
    SCHEDULER_READ = "scheduler:read"
    SCHEDULER_MANAGE = "scheduler:manage"
    BACKUPS_KEYS = "backups:keys"
    BACKUPS_EXPORT = "backups:export"
    BACKUPS_DESTINATIONS = "backups:destinations"
    CONTENT_MANAGE = "content:manage"
    WORLDS_READ = "worlds:read"
    WORLDS_MANAGE = "worlds:manage"
    WORLDS_RESET = "worlds:reset"
    ADDONS_MANAGE = "addons:manage"
    DOWNLOADS_PRUNE = "downloads:prune"
    RUNTIME_READ = "runtime:read"
    RUNTIME_SHUTDOWN = "runtime:shutdown"
    BANS_READ = "bans:read"
    BANS_MANAGE = "bans:manage"


CORE_DESCRIPTIONS: MappingProxyType[str, str] = MappingProxyType(
    {
        Permission.HEALTH_READ: "Check application health and readiness",
        Permission.SESSIONS_MANAGE: "Manage your login sessions and security settings",
        Permission.SESSIONS_ADMIN: "Inspect or revoke account logins and reset other accounts' MFA",
        Permission.TOKENS_MANAGE: "Manage your integration credentials",
        Permission.ACCESS_MANAGE: "Inspect credentials and change other accounts' server assignments",
        Permission.ACCOUNT_READ: "Read your account identity and effective access",
        Permission.ACCOUNT_MANAGE: "Change your profile, appearance and password",
        Permission.SERVERS_READ: "List visible servers and read their status and resource usage",
        Permission.TASKS_READ: "Read your background tasks within current credential and server access",
        Permission.PLUGINS_PAGES: "Discover registered plugin UI pages",
        Permission.RUNTIME_METRICS: "Read application and host performance metrics",
        Permission.SERVERS_INSPECT: "Inspect server details and configuration summaries",
        Permission.SERVERS_LIFECYCLE: "Start, stop and restart game servers",
        Permission.SERVERS_COMMAND: "Send interactive console commands to running servers",
        Permission.PROPERTIES_READ: "Read server.properties configuration",
        Permission.PROPERTIES_MANAGE: "Edit server.properties configuration",
        Permission.PLAYERS_READ: "Read the global known-player directory",
        Permission.PLAYERS_MANAGE: "Scan all server logs or edit the global player directory",
        Permission.ALLOWLIST_READ: "Read a server allowlist",
        Permission.ALLOWLIST_MANAGE: "Add or remove allowlisted players",
        Permission.PERMISSIONS_READ: "Read Minecraft player permission levels",
        Permission.PERMISSIONS_MANAGE: "Change Minecraft player permission levels, including operator access",
        Permission.USERS_READ: "Read application user accounts",
        Permission.LOGS_READ: "Read logs for authorized servers",
        Permission.BACKUPS_READ: "List, inspect and download stored backup archives",
        Permission.BACKUPS_CREATE: "Create backups of authorized servers",
        Permission.BACKUPS_RESTORE: "Plan and restore server data; restores may stop a running server",
        Permission.BACKUPS_MANAGE: "Import, verify, drill and pin server backups",
        Permission.BACKUPS_PRUNE: "Prune server backups using configured retention",
        Permission.CONTENT_READ: "Read shared world and add-on template libraries",
        Permission.ADDONS_READ: "Read installed server add-ons and pack icons",
        Permission.DOWNLOADS_READ: "Read cached custom server download archives",
        Permission.SERVERS_CONFIGURE: "Change managed server settings such as automatic updates",
        Permission.SERVERS_INSTALL: "Install new servers and update server software binaries",
        Permission.SERVERS_DELETE: "Delete servers and all associated server data",
        Permission.USERS_MANAGE: "Create invitations and administer application accounts and roles",
        Permission.SETTINGS_READ: "Read installation-wide application settings",
        Permission.SETTINGS_MANAGE: "Change installation-wide application settings",
        Permission.LOGS_READ_APPLICATION: "Read application logs across the installation",
        Permission.DIAGNOSTICS_READ: "Inspect runtime, event and activity diagnostics",
        Permission.AUDIT_READ: "Read installation-wide administrative audit history",
        Permission.PLUGINS_READ: "Read plugin status and metadata",
        Permission.PLUGINS_MANAGE: "Configure, enable or reload plugins and trigger plugin events",
        Permission.SCHEDULER_READ: "Read global schedules and run history",
        Permission.SCHEDULER_MANAGE: "Create, change, delete or run global scheduled work",
        Permission.BACKUPS_KEYS: "Manage backup encryption keys and export secret recovery credentials",
        Permission.BACKUPS_EXPORT: "Export decrypted backup contents",
        Permission.BACKUPS_DESTINATIONS: "Prepare server copies and clean up external backup destinations",
        Permission.CONTENT_MANAGE: "Upload or delete shared world and add-on template files",
        Permission.WORLDS_READ: "Read server world metadata and icons",
        Permission.WORLDS_MANAGE: "Import or export Minecraft server worlds",
        Permission.WORLDS_RESET: "Reset and regenerate server worlds",
        Permission.ADDONS_MANAGE: "Install, enable, disable, uninstall or reorder server add-ons",
        Permission.DOWNLOADS_PRUNE: "Prune cached server download archives",
        Permission.RUNTIME_READ: "Inspect the hosting web runtime",
        Permission.RUNTIME_SHUTDOWN: "Shut down the hosting web runtime",
        Permission.BANS_READ: "Read server player bans",
        Permission.BANS_MANAGE: "Ban or unban players on a server",
    }
)

_USER_GRANTS: frozenset[str] = frozenset(
    {
        Permission.HEALTH_READ,
        Permission.TOKENS_MANAGE,
        Permission.SESSIONS_MANAGE,
        Permission.ACCOUNT_READ,
        Permission.ACCOUNT_MANAGE,
        Permission.SERVERS_READ,
        Permission.WORLDS_READ,
        Permission.TASKS_READ,
        Permission.PLUGINS_PAGES,
        Permission.RUNTIME_METRICS,
    }
)

_MODERATOR_GRANTS: frozenset[str] = _USER_GRANTS | frozenset(
    {
        Permission.SERVERS_INSPECT,
        Permission.SERVERS_LIFECYCLE,
        Permission.SERVERS_COMMAND,
        Permission.PROPERTIES_READ,
        Permission.PROPERTIES_MANAGE,
        Permission.PLAYERS_READ,
        Permission.PLAYERS_MANAGE,
        Permission.ALLOWLIST_READ,
        Permission.ALLOWLIST_MANAGE,
        Permission.PERMISSIONS_READ,
        Permission.PERMISSIONS_MANAGE,
        Permission.USERS_READ,
        Permission.LOGS_READ,
        Permission.BACKUPS_READ,
        Permission.BACKUPS_CREATE,
        Permission.BACKUPS_RESTORE,
        Permission.BACKUPS_MANAGE,
        Permission.BACKUPS_PRUNE,
        Permission.CONTENT_READ,
        Permission.ADDONS_READ,
        Permission.DOWNLOADS_READ,
    }
)

_ADMIN_GRANTS: frozenset[str] = _MODERATOR_GRANTS | frozenset(
    {
        Permission.SERVERS_CONFIGURE,
        Permission.SERVERS_INSTALL,
        Permission.SERVERS_DELETE,
        Permission.USERS_MANAGE,
        Permission.SETTINGS_READ,
        Permission.SETTINGS_MANAGE,
        Permission.LOGS_READ_APPLICATION,
        Permission.DIAGNOSTICS_READ,
        Permission.AUDIT_READ,
        Permission.PLUGINS_READ,
        Permission.PLUGINS_MANAGE,
        Permission.SCHEDULER_READ,
        Permission.SCHEDULER_MANAGE,
        Permission.BACKUPS_KEYS,
        Permission.BACKUPS_EXPORT,
        Permission.BACKUPS_DESTINATIONS,
        Permission.CONTENT_MANAGE,
        Permission.WORLDS_MANAGE,
        Permission.WORLDS_RESET,
        Permission.ADDONS_MANAGE,
        Permission.DOWNLOADS_PRUNE,
        Permission.RUNTIME_READ,
        Permission.RUNTIME_SHUTDOWN,
        Permission.BANS_READ,
        Permission.ACCESS_MANAGE,
        Permission.SESSIONS_ADMIN,
        Permission.BANS_MANAGE,
    }
)

ROLE_GRANTS = MappingProxyType(
    {
        "user": _USER_GRANTS,
        "moderator": _MODERATOR_GRANTS,
        "admin": _ADMIN_GRANTS,
    }
)


@dataclass(frozen=True)
class PluginPermission:
    owner: str
    description: str
    roles: frozenset[str]
    server_scoped: bool = False


class AccessPolicy:
    """One registry per application; plugin grants never imply an admin bypass."""

    def __init__(self, changed: Callable[[], None] | None = None):
        self._plugins: dict[str, PluginPermission] = {}
        self._epoch = uuid4().hex
        self._revision = 0
        self._schema_owners: WeakSet = WeakSet()
        self.changed = changed or (lambda: None)

    @property
    def revision(self) -> str:
        return f"{self._epoch}:{self._revision}"

    def bind_schema(self, app) -> None:
        self._schema_owners.add(app)

    def touch(self) -> None:
        self._revision += 1
        for app in self._schema_owners:
            app.openapi_schema = None
        self.changed()

    @property
    def descriptions(self) -> dict[str, str]:
        return {
            **CORE_DESCRIPTIONS,
            **{key: value.description for key, value in self._plugins.items()},
        }

    @property
    def server_permissions(self) -> frozenset[str]:
        from .authorization import SERVER_PERMISSIONS

        return SERVER_PERMISSIONS | frozenset(
            key for key, value in self._plugins.items() if value.server_scoped
        )

    def resolve(self, role: str) -> frozenset[str]:
        return ROLE_GRANTS.get(role, frozenset()) | frozenset(
            key for key, value in self._plugins.items() if role in value.roles
        )

    def validate(self, permissions) -> None:
        unknown = set(permissions) - self.descriptions.keys()
        if unknown:
            raise ValueError(f"Unknown permissions: {sorted(unknown)}")

    def register(
        self,
        owner: str,
        permission: str,
        description: str,
        roles,
        *,
        server_scoped: bool = False,
    ) -> None:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", owner):
            raise ValueError("Invalid plugin owner")
        if not permission.startswith(f"plugin:{owner}:") or not re.fullmatch(
            r"plugin:[A-Za-z0-9_.-]+:[a-z][a-z0-9_-]*(?::[a-z][a-z0-9_-]*)*", permission
        ):
            raise ValueError("Plugin permissions must use their owner's namespace")
        grants = frozenset(roles)
        if not grants or not grants <= ROLE_GRANTS.keys() or not description.strip():
            raise ValueError(
                "A description and valid explicit role grants are required"
            )
        if permission in self.descriptions:
            raise ValueError(f"Permission already registered: {permission}")
        self._plugins[permission] = PluginPermission(
            owner, description, grants, server_scoped=bool(server_scoped)
        )
        self.touch()

    def remove_owner(self, owner: str) -> None:
        removed = [key for key, value in self._plugins.items() if value.owner == owner]
        for key in removed:
            del self._plugins[key]
        if removed:
            self.touch()


def policy_for(request) -> AccessPolicy:
    return cast(AccessPolicy, request.app.state.access_policy)
