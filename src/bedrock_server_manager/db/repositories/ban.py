"""
Repository for managing ServerBan database entity operations.
"""

from typing import Any, Optional

from sqlalchemy.future import select

from ...state.models import BanItem, BanResult
from ..models import Server, ServerBan


class ServerBanRepository:
    """Handles database operations for server bans."""

    def __init__(self, db: Any = None):
        self.db = db

    async def add_or_update_ban(
        self,
        session: Any,
        server_name: str,
        player_name: str,
        xuid: str,
        reason: Optional[str] = None,
    ) -> BanResult:
        """Adds or updates a server ban record in the given session."""
        result = await session.execute(
            select(Server).filter(Server.server_name == server_name)
        )
        server = result.scalar_one_or_none()
        if not server:
            return BanResult(
                success=False,
                message=f"Server '{server_name}' not found in database.",
            )

        result = await session.execute(
            select(ServerBan).filter(
                ServerBan.server_id == server.id, ServerBan.xuid == xuid
            )
        )
        existing_ban = result.scalar_one_or_none()

        if existing_ban:
            existing_ban.reason = reason
            return BanResult(
                success=True,
                message=f"Ban updated for player '{player_name}'.",
            )

        new_ban = ServerBan(
            server_id=server.id, player_name=player_name, xuid=xuid, reason=reason
        )
        session.add(new_ban)
        return BanResult(
            success=True,
            message=f"Player '{player_name}' banned successfully.",
        )

    async def remove_ban(self, session: Any, server_name: str, xuid: str) -> BanResult:
        """Removes a server ban record by XUID in the given session."""
        result = await session.execute(
            select(Server).filter(Server.server_name == server_name)
        )
        server = result.scalar_one_or_none()
        if not server:
            return BanResult(
                success=False,
                message=f"Server '{server_name}' not found in database.",
            )

        result = await session.execute(
            select(ServerBan).filter(
                ServerBan.server_id == server.id, ServerBan.xuid == xuid
            )
        )
        ban = result.scalar_one_or_none()

        if not ban:
            return BanResult(
                success=False,
                message=f"Ban not found for XUID '{xuid}' on server '{server_name}'.",
            )

        await session.delete(ban)
        return BanResult(success=True, message="Ban removed successfully.")

    async def get_bans(self, session: Any, server_name: str) -> BanResult:
        """Retrieves all bans for a specific server in the given session."""
        result = await session.execute(
            select(Server).filter(Server.server_name == server_name)
        )
        server = result.scalar_one_or_none()
        if not server:
            return BanResult(
                success=False,
                message=f"Server '{server_name}' not found in database.",
            )

        result = await session.execute(
            select(ServerBan).filter(ServerBan.server_id == server.id)
        )
        bans = result.scalars().all()
        ban_list = [
            BanItem(
                player_name=ban.player_name,
                xuid=ban.xuid,
                reason=ban.reason,
                banned_at=ban.banned_at.isoformat() if ban.banned_at else None,
            )
            for ban in bans
        ]

        return BanResult(
            success=True, message="Bans retrieved successfully.", bans=ban_list
        )
