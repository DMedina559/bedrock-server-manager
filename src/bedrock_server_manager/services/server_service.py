# src/bedrock_server_manager/services/server_service.py
"""
Service managing server domain state mutations and business rules.
"""

from typing import TYPE_CHECKING, Dict, Optional

from pydantic import JsonValue

from ..state.changeset import ChangeSet
from ..state.models import BanResult, ServerConfigState
from ..state.updates import ServerUpdate

if TYPE_CHECKING:
    from ..db.storage import Storage
    from ..state.app_state import AppState


class ServerService:
    """Handles business logic and mutations for Bedrock servers."""

    def __init__(
        self,
        state: "AppState",
        storage: "Storage",
    ):
        self.state = state
        self.storage = storage

    def get_server_state(self, server_name: str) -> Optional[ServerConfigState]:
        """Retrieves a server configuration state model snapshot."""
        cfg = self.state.servers.get(server_name)
        if cfg:
            res: ServerConfigState = cfg.model_copy()
            return res
        return None

    async def register_or_update_server(
        self,
        server_name: str,
        installed_version: Optional[str] = None,
        status: Optional[str] = None,
        autoupdate: Optional[bool] = None,
        autostart: Optional[bool] = None,
        target_version: Optional[str] = None,
        custom: Optional[Dict[str, JsonValue]] = None,
    ) -> ServerConfigState:
        """Registers or updates server state model while maintaining dirty tracking."""
        async with self.state.servers.get_lock(server_name):
            existing = self.state.servers.get(server_name)
            values: dict[str, object] = {"server_name": server_name}
            for name, value in (
                ("installed_version", installed_version),
                ("status", status),
                ("autoupdate", autoupdate),
                ("autostart", autostart),
                ("target_version", target_version),
                ("custom", custom),
            ):
                if value is not None:
                    values[name] = value
            update = ServerUpdate.model_validate(values)
            data = existing.model_dump() if existing else {}
            data.update(update.model_dump(exclude_unset=True))
            config = ServerConfigState.model_validate(data)

            self.state.servers.set(config)

        changeset = ChangeSet()
        changeset.add_server(server_name)

        await self.storage.apply_changeset(self.state, changeset)

        return config

    async def set_autostart(self, server_name: str, enabled: bool) -> None:
        """Sets server autostart flag."""
        await self.register_or_update_server(server_name, autostart=enabled)

    async def set_autoupdate(self, server_name: str, enabled: bool) -> None:
        """Sets server autoupdate flag."""
        await self.register_or_update_server(server_name, autoupdate=enabled)

    async def add_server_ban(
        self,
        server_name: str,
        player_name: str,
        xuid: str,
        reason: Optional[str] = None,
    ) -> BanResult:
        """Adds or updates a server ban record."""
        async with self.storage.transaction() as session:
            return await self.storage.ban_repo.add_or_update_ban(
                session, server_name, player_name, xuid, reason
            )

    async def remove_server_ban(self, server_name: str, xuid: str) -> BanResult:
        """Removes a server ban record by XUID."""
        async with self.storage.transaction() as session:
            return await self.storage.ban_repo.remove_ban(session, server_name, xuid)

    async def get_server_bans(self, server_name: str) -> BanResult:
        """Retrieves all bans for a specific server."""
        async with self.storage.transaction() as session:
            return await self.storage.ban_repo.get_bans(session, server_name)
