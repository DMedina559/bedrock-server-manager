"""Canonical built-in capabilities shared by HTTP and plugin adapters."""

from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Literal


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
    SERVERS_LOGS = "servers:logs"
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
    APPLICATION_LOGS = "application:logs"
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


@dataclass(frozen=True)
class PermissionSpec:
    description: str
    roles: tuple[str, ...] = ("admin",)
    resource: Literal["global", "server", "personal"] = "global"
    delegatable: bool = True
    step_up: bool = False


PERMISSION_SPECS = MappingProxyType(
    {
        Permission.HEALTH_READ: PermissionSpec(
            "Check application health and readiness",
            roles=("user", "moderator", "admin"),
            resource="personal",
        ),
        Permission.TOKENS_MANAGE: PermissionSpec(
            "Manage your integration credentials",
            roles=("user", "moderator", "admin"),
            resource="personal",
            delegatable=False,
        ),
        Permission.SESSIONS_MANAGE: PermissionSpec(
            "Manage your login sessions and security settings",
            roles=("user", "moderator", "admin"),
            resource="personal",
            delegatable=False,
        ),
        Permission.SESSIONS_ADMIN: PermissionSpec(
            "Inspect or revoke account logins and reset other accounts' MFA",
            delegatable=False,
            step_up=True,
        ),
        Permission.ACCESS_MANAGE: PermissionSpec(
            "Inspect credentials and change other accounts' server assignments",
            delegatable=False,
            step_up=True,
        ),
        Permission.ACCOUNT_READ: PermissionSpec(
            "Read your account identity and effective access",
            roles=("user", "moderator", "admin"),
            resource="personal",
        ),
        Permission.ACCOUNT_MANAGE: PermissionSpec(
            "Change your profile, appearance and password",
            roles=("user", "moderator", "admin"),
            resource="personal",
            delegatable=False,
        ),
        Permission.SERVERS_READ: PermissionSpec(
            "List visible servers and read their status and resource usage",
            roles=("user", "moderator", "admin"),
            resource="server",
        ),
        Permission.TASKS_READ: PermissionSpec(
            "Read your background tasks within current credential and server access",
            roles=("user", "moderator", "admin"),
            resource="personal",
        ),
        Permission.PLUGINS_PAGES: PermissionSpec(
            "Discover registered plugin UI pages", roles=("user", "moderator", "admin")
        ),
        Permission.RUNTIME_METRICS: PermissionSpec(
            "Read application and host performance metrics",
            roles=("user", "moderator", "admin"),
        ),
        Permission.SERVERS_INSPECT: PermissionSpec(
            "Inspect server details and configuration summaries",
            roles=("moderator", "admin"),
            resource="server",
        ),
        Permission.SERVERS_LIFECYCLE: PermissionSpec(
            "Start, stop and restart game servers",
            roles=("moderator", "admin"),
            resource="server",
        ),
        Permission.SERVERS_COMMAND: PermissionSpec(
            "Send interactive console commands to running servers",
            roles=("moderator", "admin"),
            resource="server",
        ),
        Permission.PROPERTIES_READ: PermissionSpec(
            "Read server.properties configuration",
            roles=("moderator", "admin"),
            resource="server",
        ),
        Permission.PROPERTIES_MANAGE: PermissionSpec(
            "Edit server.properties configuration",
            roles=("moderator", "admin"),
            resource="server",
        ),
        Permission.PLAYERS_READ: PermissionSpec(
            "Read the global known-player directory", roles=("moderator", "admin")
        ),
        Permission.PLAYERS_MANAGE: PermissionSpec(
            "Scan all server logs or edit the global player directory",
            roles=("moderator", "admin"),
        ),
        Permission.ALLOWLIST_READ: PermissionSpec(
            "Read a server allowlist", roles=("moderator", "admin"), resource="server"
        ),
        Permission.ALLOWLIST_MANAGE: PermissionSpec(
            "Add or remove allowlisted players",
            roles=("moderator", "admin"),
            resource="server",
        ),
        Permission.PERMISSIONS_READ: PermissionSpec(
            "Read Minecraft player permission levels",
            roles=("moderator", "admin"),
            resource="server",
        ),
        Permission.PERMISSIONS_MANAGE: PermissionSpec(
            "Change Minecraft player permission levels, including operator access",
            roles=("moderator", "admin"),
            resource="server",
        ),
        Permission.USERS_READ: PermissionSpec(
            "Read application user accounts", roles=("moderator", "admin")
        ),
        Permission.SERVERS_LOGS: PermissionSpec(
            "Read logs for authorized servers",
            roles=("moderator", "admin"),
            resource="server",
        ),
        Permission.BACKUPS_READ: PermissionSpec(
            "List, inspect and download stored backup archives",
            roles=("moderator", "admin"),
            resource="server",
        ),
        Permission.BACKUPS_CREATE: PermissionSpec(
            "Create backups of authorized servers",
            roles=("moderator", "admin"),
            resource="server",
        ),
        Permission.BACKUPS_RESTORE: PermissionSpec(
            "Plan and restore server data; restores may stop a running server",
            roles=("moderator", "admin"),
            resource="server",
        ),
        Permission.BACKUPS_MANAGE: PermissionSpec(
            "Import, verify, drill and pin server backups",
            roles=("moderator", "admin"),
            resource="server",
        ),
        Permission.BACKUPS_PRUNE: PermissionSpec(
            "Prune server backups using configured retention",
            roles=("moderator", "admin"),
            resource="server",
        ),
        Permission.CONTENT_READ: PermissionSpec(
            "Read shared world and add-on template libraries",
            roles=("moderator", "admin"),
            resource="server",
        ),
        Permission.ADDONS_READ: PermissionSpec(
            "Read installed server add-ons and pack icons",
            roles=("moderator", "admin"),
            resource="server",
        ),
        Permission.DOWNLOADS_READ: PermissionSpec(
            "Read cached custom server download archives", roles=("moderator", "admin")
        ),
        Permission.SERVERS_CONFIGURE: PermissionSpec(
            "Change managed server settings such as automatic updates",
            resource="server",
        ),
        Permission.SERVERS_INSTALL: PermissionSpec(
            "Install new servers and update server software binaries", resource="server"
        ),
        Permission.SERVERS_DELETE: PermissionSpec(
            "Delete servers and all associated server data", resource="server"
        ),
        Permission.USERS_MANAGE: PermissionSpec(
            "Create invitations and administer application accounts and roles",
            delegatable=False,
            step_up=True,
        ),
        Permission.SETTINGS_READ: PermissionSpec(
            "Read installation-wide application settings"
        ),
        Permission.SETTINGS_MANAGE: PermissionSpec(
            "Change installation-wide application settings"
        ),
        Permission.APPLICATION_LOGS: PermissionSpec(
            "Read application logs across the installation"
        ),
        Permission.DIAGNOSTICS_READ: PermissionSpec(
            "Inspect runtime, event and activity diagnostics"
        ),
        Permission.AUDIT_READ: PermissionSpec(
            "Read installation-wide administrative audit history"
        ),
        Permission.PLUGINS_READ: PermissionSpec("Read plugin status and metadata"),
        Permission.PLUGINS_MANAGE: PermissionSpec(
            "Configure, enable or reload plugins and trigger plugin events"
        ),
        Permission.SCHEDULER_READ: PermissionSpec(
            "Read global schedules and run history"
        ),
        Permission.SCHEDULER_MANAGE: PermissionSpec(
            "Configure and run installation-wide automation, including commands, updates, world resets and maintenance; jobs run as the application"
        ),
        Permission.BACKUPS_KEYS: PermissionSpec(
            "Manage backup encryption keys and export secret recovery credentials"
        ),
        Permission.BACKUPS_EXPORT: PermissionSpec(
            "Export decrypted backup contents", resource="server"
        ),
        Permission.BACKUPS_DESTINATIONS: PermissionSpec(
            "Prepare server copies and clean up external backup destinations",
            resource="server",
        ),
        Permission.CONTENT_MANAGE: PermissionSpec(
            "Upload or delete shared world and add-on template files", resource="server"
        ),
        Permission.WORLDS_READ: PermissionSpec(
            "Read server world metadata and icons",
            roles=("user", "moderator", "admin"),
            resource="server",
        ),
        Permission.WORLDS_MANAGE: PermissionSpec(
            "Import or export Minecraft server worlds", resource="server"
        ),
        Permission.WORLDS_RESET: PermissionSpec(
            "Reset and regenerate server worlds", resource="server"
        ),
        Permission.ADDONS_MANAGE: PermissionSpec(
            "Install, enable, disable, uninstall or reorder server add-ons",
            resource="server",
        ),
        Permission.DOWNLOADS_PRUNE: PermissionSpec(
            "Prune cached server download archives"
        ),
        Permission.RUNTIME_READ: PermissionSpec("Inspect the hosting web runtime"),
        Permission.RUNTIME_SHUTDOWN: PermissionSpec(
            "Shut down the hosting web runtime"
        ),
        Permission.BANS_READ: PermissionSpec(
            "Read server player bans", resource="server"
        ),
        Permission.BANS_MANAGE: PermissionSpec(
            "Ban or unban players on a server", resource="server"
        ),
    }
)

CORE_DESCRIPTIONS: MappingProxyType[str, str] = MappingProxyType(
    {str(key): spec.description for key, spec in PERMISSION_SPECS.items()}
)
ROLE_GRANTS: MappingProxyType[str, frozenset[str]] = MappingProxyType(
    {
        role: frozenset(
            str(key) for key, spec in PERMISSION_SPECS.items() if role in spec.roles
        )
        for role in ("user", "moderator", "admin")
    }
)
SERVER_PERMISSIONS = frozenset(
    key for key, spec in PERMISSION_SPECS.items() if spec.resource == "server"
)
PERSONAL_PERMISSIONS = frozenset(
    key for key, spec in PERMISSION_SPECS.items() if spec.resource == "personal"
)
NON_DELEGATABLE = frozenset(
    key for key, spec in PERMISSION_SPECS.items() if not spec.delegatable
)
STEP_UP_PERMISSIONS = frozenset(
    key for key, spec in PERMISSION_SPECS.items() if spec.step_up
)
