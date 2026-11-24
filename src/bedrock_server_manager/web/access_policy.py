"""Role-derived HTTP capabilities. These are endpoint scopes, not token grants."""

import re
from dataclasses import dataclass
from typing import Callable, cast
from uuid import uuid4
from weakref import WeakSet

from ..permissions import CORE_DESCRIPTIONS as CORE_DESCRIPTIONS
from ..permissions import ROLE_GRANTS as ROLE_GRANTS
from ..permissions import Permission as Permission

__all__ = [
    "Permission",
    "CORE_DESCRIPTIONS",
    "ROLE_GRANTS",
    "AccessPolicy",
    "PluginPermission",
    "policy_for",
]


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
