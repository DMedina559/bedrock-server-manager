# src/bedrock_server_manager/services/server_service.py
"""
Service managing server domain state mutations and business rules.
"""

from typing import TYPE_CHECKING, Any, Dict, Optional, cast

from ..state.changeset import ChangeSet
from ..state.models import ServerConfigState

if TYPE_CHECKING:
    from ..context import AppContext


class ServerService:
    """Handles business logic and mutations for Bedrock servers."""

    def __init__(
        self,
        app_context: Optional["AppContext"] = None,
        state: Optional[Any] = None,
        storage: Optional[Any] = None,
    ):
        self._app_context = app_context
        self._state = state
        self._storage = storage

    @property
    def app_context(self) -> Optional["AppContext"]:
        return self._app_context

    @property
    def state(self) -> Any:
        if self._state is not None:
            return self._state
        if self._app_context is not None:
            return self._app_context.state
        raise ValueError(
            "ServerService has no AppState provided or set via AppContext."
        )

    @property
    def storage(self) -> Optional[Any]:
        if self._storage is not None:
            return self._storage
        if (
            self._app_context is not None
            and getattr(self._app_context, "_storage", None) is not None
        ):
            return self._app_context.storage
        return None

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
    ) -> Dict[str, Any]:
        """Adds or updates a server ban record."""
        if (
            self.app_context is not None
            and getattr(self.app_context, "_db", None) is None
        ):
            return {"status": "error", "message": "Database is not initialized."}
        st = self.storage
        if st is None or getattr(st, "db", None) is None:
            return {"status": "error", "message": "Database is not initialized."}

        async with st.transaction() as session:
            res = await st.ban_repo.add_or_update_ban(
                session, server_name, player_name, xuid, reason
            )
            return cast(Dict[str, Any], res)

    async def remove_server_ban(self, server_name: str, xuid: str) -> Dict[str, Any]:
        """Removes a server ban record by XUID."""
        if (
            self.app_context is not None
            and getattr(self.app_context, "_db", None) is None
        ):
            return {"status": "error", "message": "Database is not initialized."}
        st = self.storage
        if st is None or getattr(st, "db", None) is None:
            return {"status": "error", "message": "Database is not initialized."}

        async with st.transaction() as session:
            res = await st.ban_repo.remove_ban(session, server_name, xuid)
            return cast(Dict[str, Any], res)

    async def get_server_bans(self, server_name: str) -> Dict[str, Any]:
        """Retrieves all bans for a specific server."""
        if (
            self.app_context is not None
            and getattr(self.app_context, "_db", None) is None
        ):
            return {"status": "error", "message": "Database is not initialized."}
        st = self.storage
        if st is None or getattr(st, "db", None) is None:
            return {"status": "error", "message": "Database is not initialized."}

        async with st.transaction() as session:
            res = await st.ban_repo.get_bans(session, server_name)
            return cast(Dict[str, Any], res)
