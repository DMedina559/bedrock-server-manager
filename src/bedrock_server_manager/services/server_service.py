# src/bedrock_server_manager/services/server_service.py
"""
Service managing server domain state mutations and business rules.
"""

from typing import TYPE_CHECKING, Any, Dict, Optional

from ..state.changeset import ChangeSet
from ..state.models import BanResult, ServerConfigState

if TYPE_CHECKING:
    from ..db.storage import Storage
    from ..state.app_state import AppState


class ServerService:
    """Handles business logic and mutations for Bedrock servers."""

    def __init__(
        self,
        state: "AppState",
        storage: Optional["Storage"] = None,
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
        installed_version: str = "UNKNOWN",
        status: str = "UNKNOWN",
        autoupdate: Optional[bool] = None,
        autostart: Optional[bool] = None,
        target_version: Optional[str] = None,
        custom: Optional[Dict[str, Any]] = None,
    ) -> ServerConfigState:
        """Registers or updates server state model while maintaining dirty tracking."""
        existing = self.state.servers.get(server_name)
        if existing:
            updated_dict = existing.model_dump()
            updated_dict["installed_version"] = installed_version
            updated_dict["status"] = status
            if autoupdate is not None:
                updated_dict["autoupdate"] = autoupdate
            if autostart is not None:
                updated_dict["autostart"] = autostart
            if target_version is not None:
                updated_dict["target_version"] = target_version
            if custom is not None:
                updated_dict["custom"] = custom
            config = ServerConfigState(**updated_dict)
        else:
            config = ServerConfigState(
                server_name=server_name,
                installed_version=installed_version,
                status=status,
                autoupdate=autoupdate if autoupdate is not None else False,
                autostart=autostart if autostart is not None else False,
                target_version=target_version or "UNKNOWN",
                custom=custom or {},
            )

        async with self.state.lock:
            self.state.servers.set(config)

            changeset = ChangeSet()
            changeset.add_server(server_name)

            if self.storage is not None and hasattr(self.storage, "apply_changeset"):
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
        st = self.storage
        if st is None or getattr(st, "db", None) is None:
            return BanResult(success=False, message="Database is not initialized.")

        async with st.transaction() as session:
            return await st.ban_repo.add_or_update_ban(
                session, server_name, player_name, xuid, reason
            )

    async def remove_server_ban(self, server_name: str, xuid: str) -> BanResult:
        """Removes a server ban record by XUID."""
        st = self.storage
        if st is None or getattr(st, "db", None) is None:
            return BanResult(success=False, message="Database is not initialized.")

        async with st.transaction() as session:
            return await st.ban_repo.remove_ban(session, server_name, xuid)

    async def get_server_bans(self, server_name: str) -> BanResult:
        """Retrieves all bans for a specific server."""
        st = self.storage
        if st is None or getattr(st, "db", None) is None:
            return BanResult(success=False, message="Database is not initialized.")

        async with st.transaction() as session:
            return await st.ban_repo.get_bans(session, server_name)
