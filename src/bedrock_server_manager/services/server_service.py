# src/bedrock_server_manager/services/server_service.py
"""
Service managing server domain state mutations and business rules.
"""

from typing import TYPE_CHECKING, Any, Dict, Optional

from sqlalchemy.future import select

from ..db.models import Server, ServerBan
from ..state.models import ServerConfigState

if TYPE_CHECKING:
    from ..context import AppContext


class ServerService:
    """Handles business logic and mutations for Bedrock servers."""

    def __init__(self, app_context: "AppContext"):
        self.app_context = app_context

    def get_server_state(self, server_name: str) -> Optional[ServerConfigState]:
        """Retrieves a server configuration state model snapshot."""
        cfg = self.app_context.state.servers.get(server_name)
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
        existing = self.app_context.state.servers.get(server_name)
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

        self.app_context.state.servers.set(config)
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
        if getattr(self.app_context, "_db", None) is None:
            return {"status": "error", "message": "Database is not initialized."}

        async with self.app_context.db.session_manager() as session:
            result = await session.execute(
                select(Server).filter(Server.server_name == server_name)
            )
            server = result.scalar_one_or_none()
            if not server:
                return {
                    "status": "error",
                    "message": f"Server '{server_name}' not found in database.",
                }

            result = await session.execute(
                select(ServerBan).filter(
                    ServerBan.server_id == server.id, ServerBan.xuid == xuid
                )
            )
            existing_ban = result.scalar_one_or_none()

            if existing_ban:
                existing_ban.reason = reason
                await session.commit()
                return {
                    "status": "success",
                    "message": f"Ban updated for player '{player_name}'.",
                }

            new_ban = ServerBan(
                server_id=server.id, player_name=player_name, xuid=xuid, reason=reason
            )
            session.add(new_ban)
            await session.commit()
            return {
                "status": "success",
                "message": f"Player '{player_name}' banned successfully.",
            }

    async def remove_server_ban(self, server_name: str, xuid: str) -> Dict[str, Any]:
        """Removes a server ban record by XUID."""
        if getattr(self.app_context, "_db", None) is None:
            return {"status": "error", "message": "Database is not initialized."}

        async with self.app_context.db.session_manager() as session:
            result = await session.execute(
                select(Server).filter(Server.server_name == server_name)
            )
            server = result.scalar_one_or_none()
            if not server:
                return {
                    "status": "error",
                    "message": f"Server '{server_name}' not found in database.",
                }

            result = await session.execute(
                select(ServerBan).filter(
                    ServerBan.server_id == server.id, ServerBan.xuid == xuid
                )
            )
            ban = result.scalar_one_or_none()

            if not ban:
                return {
                    "status": "error",
                    "message": f"Ban not found for XUID '{xuid}' on server '{server_name}'.",
                }

            await session.delete(ban)
            await session.commit()
            return {"status": "success", "message": "Ban removed successfully."}

    async def get_server_bans(self, server_name: str) -> Dict[str, Any]:
        """Retrieves all bans for a specific server."""
        if getattr(self.app_context, "_db", None) is None:
            return {"status": "error", "message": "Database is not initialized."}

        async with self.app_context.db.session_manager() as session:
            result = await session.execute(
                select(Server).filter(Server.server_name == server_name)
            )
            server = result.scalar_one_or_none()
            if not server:
                return {
                    "status": "error",
                    "message": f"Server '{server_name}' not found in database.",
                }

            result = await session.execute(
                select(ServerBan).filter(ServerBan.server_id == server.id)
            )
            bans = result.scalars().all()
            ban_list = [
                {
                    "player_name": ban.player_name,
                    "xuid": ban.xuid,
                    "reason": ban.reason,
                    "banned_at": ban.banned_at.isoformat() if ban.banned_at else None,
                }
                for ban in bans
            ]

            return {"status": "success", "bans": ban_list}
