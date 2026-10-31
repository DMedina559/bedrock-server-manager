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
        "health:read": "Read application readiness",
        "sessions:manage": "Manage your login sessions and security settings",
        "sessions:admin": "Inspect and revoke account login sessions",
        "tokens:manage": "Manage your integration credentials",
        "access:manage": "Manage account server access",
        "account:read": "Account read",
        "account:manage": "Account manage",
        "servers:read": "Servers read",
        "tasks:read": "Tasks read",
        "plugins:pages": "Plugins pages",
        "runtime:metrics": "Runtime metrics",
        "servers:inspect": "Servers inspect",
        "servers:control": "Servers control",
        "servers:properties": "Servers properties",
        "players:read": "Players read",
        "players:manage": "Players manage",
        "allowlist:read": "Allowlist read",
        "allowlist:manage": "Allowlist manage",
        "permissions:read": "Permissions read",
        "permissions:manage": "Permissions manage",
        "users:read": "Users read",
        "logs:read": "Logs read",
        "backups:read": "Backups read",
        "backups:create": "Backups create",
        "backups:restore": "Backups restore",
        "backups:manage": "Backups manage",
        "content:read": "Content read",
        "servers:configure": "Servers configure",
        "servers:manage": "Servers manage",
        "users:manage": "Users manage",
        "settings:read": "Settings read",
        "settings:manage": "Settings manage",
        "logs:read_application": "Logs read application",
        "diagnostics:read": "Diagnostics read",
        "audit:read": "Audit read",
        "plugins:read": "Plugins read",
        "plugins:manage": "Plugins manage",
        "scheduler:read": "Scheduler read",
        "scheduler:manage": "Scheduler manage",
        "backups:keys": "Backups keys",
        "backups:export": "Backups export",
        "backups:destinations": "Backups destinations",
        "content:manage": "Content manage",
        "runtime:read": "Runtime read",
        "runtime:shutdown": "Runtime shutdown",
        "bans:read": "Bans read",
        "bans:manage": "Bans manage",
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
