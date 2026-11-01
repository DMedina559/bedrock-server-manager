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
    SERVERS_CONTROL = "servers:control"
    SERVERS_PROPERTIES = "servers:properties"
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
    CONTENT_READ = "content:read"
    SERVERS_CONFIGURE = "servers:configure"
    SERVERS_MANAGE = "servers:manage"
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
    RUNTIME_READ = "runtime:read"
    RUNTIME_SHUTDOWN = "runtime:shutdown"
    BANS_READ = "bans:read"
    BANS_MANAGE = "bans:manage"


CORE_DESCRIPTIONS = MappingProxyType(
    {
        "health:read": "Check application health and readiness",
        "sessions:manage": "Manage your login sessions and security settings",
        "sessions:admin": "Inspect or revoke account logins and reset other accounts' MFA",
        "tokens:manage": "Manage your integration credentials",
        "access:manage": "Inspect credentials and change other accounts' server assignments",
        "account:read": "Read your account identity and effective access",
        "account:manage": "Change your profile, appearance and password",
        "servers:read": "List visible servers and read their status and resource usage",
        "tasks:read": "Read your background tasks within current credential and server access",
        "plugins:pages": "Discover registered plugin UI pages",
        "runtime:metrics": "Read application and host performance metrics",
        "servers:inspect": "Inspect server details and configuration summaries",
        "servers:control": "Start, stop and restart servers or send console commands",
        "servers:properties": "Read and edit server.properties",
        "players:read": "Read the global known-player directory",
        "players:manage": "Scan all server logs or edit the global player directory",
        "allowlist:read": "Read a server allowlist",
        "allowlist:manage": "Add or remove allowlisted players",
        "permissions:read": "Read Minecraft player permission levels",
        "permissions:manage": "Change Minecraft player permission levels, including operator access",
        "users:read": "Read application user accounts",
        "logs:read": "Read logs for authorized servers",
        "backups:read": "List, inspect and download stored backup archives",
        "backups:create": "Create backups of authorized servers",
        "backups:restore": "Plan and restore server data; restores may stop a running server",
        "backups:manage": "Import, verify, pin and prune server backups",
        "content:read": "Read world and add-on inventories",
        "servers:configure": "Change managed server settings such as automatic updates",
        "servers:manage": "Install, update, rename or delete servers and their data",
        "users:manage": "Create invitations and administer application accounts and roles",
        "settings:read": "Read installation-wide application settings",
        "settings:manage": "Change installation-wide application settings",
        "logs:read_application": "Read application logs across the installation",
        "diagnostics:read": "Inspect runtime, event and activity diagnostics",
        "audit:read": "Read installation-wide administrative audit history",
        "plugins:read": "Read plugin status and metadata",
        "plugins:manage": "Configure, enable or reload plugins and trigger plugin events",
        "scheduler:read": "Read global schedules and run history",
        "scheduler:manage": "Create, change, delete or run global scheduled work",
        "backups:keys": "Manage backup encryption keys and export secret recovery credentials",
        "backups:export": "Export decrypted backup contents",
        "backups:destinations": "Prepare server copies and clean up external backup destinations",
        "content:manage": "Import, export, remove or change worlds and add-ons",
        "runtime:read": "Inspect the hosting web runtime",
        "runtime:shutdown": "Shut down the hosting web runtime",
        "bans:read": "Read server player bans",
        "bans:manage": "Ban or unban players on a server",
    }
)

ROLE_GRANTS = MappingProxyType(
    {
        "user": frozenset(
            [
                "health:read",
                "tokens:manage",
                "sessions:manage",
                "account:read",
                "account:manage",
                "servers:read",
                "tasks:read",
                "plugins:pages",
                "runtime:metrics",
            ]
        ),
        "moderator": frozenset(
            [
                "health:read",
                "tokens:manage",
                "sessions:manage",
                "account:read",
                "account:manage",
                "servers:read",
                "tasks:read",
                "plugins:pages",
                "runtime:metrics",
                "servers:inspect",
                "servers:control",
                "servers:properties",
                "players:read",
                "players:manage",
                "allowlist:read",
                "allowlist:manage",
                "permissions:read",
                "permissions:manage",
                "users:read",
                "logs:read",
                "backups:read",
                "backups:create",
                "backups:restore",
                "backups:manage",
                "content:read",
            ]
        ),
        "admin": frozenset(
            [
                "health:read",
                "tokens:manage",
                "sessions:manage",
                "account:read",
                "account:manage",
                "servers:read",
                "tasks:read",
                "plugins:pages",
                "runtime:metrics",
                "servers:inspect",
                "servers:control",
                "servers:properties",
                "players:read",
                "players:manage",
                "allowlist:read",
                "allowlist:manage",
                "permissions:read",
                "permissions:manage",
                "users:read",
                "logs:read",
                "backups:read",
                "backups:create",
                "backups:restore",
                "backups:manage",
                "content:read",
                "servers:configure",
                "servers:manage",
                "users:manage",
                "settings:read",
                "settings:manage",
                "logs:read_application",
                "diagnostics:read",
                "audit:read",
                "plugins:read",
                "plugins:manage",
                "scheduler:read",
                "scheduler:manage",
                "backups:keys",
                "backups:export",
                "backups:destinations",
                "content:manage",
                "runtime:read",
                "runtime:shutdown",
                "bans:read",
                "access:manage",
                "sessions:admin",
                "bans:manage",
            ]
        ),
    }
)


@dataclass(frozen=True)
class PluginPermission:
    owner: str
    description: str
    roles: frozenset[str]


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

    def resolve(self, role: str) -> frozenset[str]:
        return ROLE_GRANTS.get(role, frozenset()) | frozenset(
            key for key, value in self._plugins.items() if role in value.roles
        )

    def validate(self, permissions) -> None:
        unknown = set(permissions) - self.descriptions.keys()
        if unknown:
            raise ValueError(f"Unknown permissions: {sorted(unknown)}")

    def register(self, owner: str, permission: str, description: str, roles) -> None:
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
        self._plugins[permission] = PluginPermission(owner, description, grants)
        self.touch()

    def remove_owner(self, owner: str) -> None:
        removed = [key for key, value in self._plugins.items() if value.owner == owner]
        for key in removed:
            del self._plugins[key]
        if removed:
            self.touch()


def policy_for(request) -> AccessPolicy:
    return cast(AccessPolicy, request.app.state.access_policy)
