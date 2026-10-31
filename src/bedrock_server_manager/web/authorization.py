"""Request-owned access snapshots. No secrets enter tasks or socket records."""

from contextvars import ContextVar
from dataclasses import dataclass

SERVER_PERMISSIONS = frozenset(
    {
        "servers:read",
        "servers:inspect",
        "servers:control",
        "servers:properties",
        "servers:configure",
        "servers:manage",
        "allowlist:read",
        "allowlist:manage",
        "permissions:read",
        "permissions:manage",
        "bans:read",
        "bans:manage",
        "logs:read",
        "backups:read",
        "backups:create",
        "backups:restore",
        "backups:manage",
        "backups:export",
        "backups:destinations",
        "content:read",
        "content:manage",
    }
)
PERSONAL_PERMISSIONS = frozenset(
    {
        "account:read",
        "account:manage",
        "tokens:manage",
        "tasks:read",
        "health:read",
        "sessions:manage",
    }
)
NON_DELEGATABLE = frozenset(
    {
        "tokens:manage",
        "access:manage",
        "account:manage",
        "users:manage",
        "sessions:manage",
        "sessions:admin",
    }
)


@dataclass(frozen=True)
class Authorization:
    user_id: int
    username: str
    owner_id: str
    permissions: frozenset[str]
    servers: dict[str, str]
    grants: dict[str, frozenset[str]] | None
    token_id: str | None = None
    token_servers: frozenset[str] | None = None
    revision: str = ""
    session_id: str | None = None

    @property
    def resource_restricted(self) -> bool:
        return self.grants is not None or self.token_servers is not None

    @property
    def restricted(self) -> bool:
        return self.token_id is not None or self.resource_restricted

    def allows(self, permission: str, server_name: str | None = None) -> bool:
        if permission not in self.permissions:
            return False
        if server_name is None:
            return not (
                self.resource_restricted and permission not in PERSONAL_PERMISSIONS
            )
        if not self.resource_restricted:
            return True
        identity = self.servers.get(server_name)
        if identity is None:
            return False
        if self.token_servers is not None and identity not in self.token_servers:
            return False
        return self.grants is None or permission in self.grants.get(
            identity, frozenset()
        )


def server_collection(endpoint):
    """Mark a collection whose handler filters each resource explicitly."""
    endpoint.__bsm_server_collection__ = True
    return endpoint


current_authorization: ContextVar[Authorization | None] = ContextVar(
    "http_authorization", default=None
)


def assigned_session(endpoint):
    """Permit ordinary assigned accounts to renew/logout, never integration tokens."""
    endpoint.__bsm_assigned_session__ = True
    return endpoint


SERVER_EVENTS = frozenset(
    {
        "event:after_server_status_change",
        "event:after_server_start",
        "event:after_server_stop",
        "event:before_server_stop",
        "event:after_delete_server_data",
        "event:after_server_update",
        "event:after_server_install",
        "event:after_server_players_change",
    }
)

operation_permissions: ContextVar[frozenset[str]] = ContextVar(
    "http_operation_permissions", default=frozenset()
)
