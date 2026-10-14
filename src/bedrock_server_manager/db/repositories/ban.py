"""
Repository for managing ServerBan database entity operations.
"""

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from ...error import ResourceNotFoundError
from ...results import BanMutation
from ...state.models import BanItem
from ..database import Database
from ..models import Server, ServerBan


class ServerBanRepository:
    """Handle database operations for server bans."""

    def __init__(self, db: Database | None = None):
        self.db = db

    async def add_or_update_ban(
        self,
        session: AsyncSession,
        server_name: str,
        player_name: str,
        xuid: str,
        reason: Optional[str] = None,
    ) -> BanMutation:
        """Adds or updates a server ban record in the given session."""
        result = await session.execute(
            select(Server).filter(Server.server_name == server_name)
        )
        server = result.scalar_one_or_none()
        if not server:
            raise ResourceNotFoundError(f"Server '{server_name}' not found.")

        ban_result = await session.execute(
            select(ServerBan).filter(
                ServerBan.server_id == server.id, ServerBan.xuid == xuid
            )
        )
        existing_ban = ban_result.scalar_one_or_none()

        if existing_ban:
            existing_ban.player_name = player_name
            existing_ban.reason = reason
            return BanMutation(
                outcome="updated",
                message=f"Ban updated for player '{player_name}'.",
            )

        new_ban = ServerBan(
            server_id=server.id, player_name=player_name, xuid=xuid, reason=reason
        )
        session.add(new_ban)
        return BanMutation(
            outcome="added",
            message=f"Player '{player_name}' banned successfully.",
        )

    async def remove_ban(
        self, session: AsyncSession, server_name: str, xuid: str
    ) -> BanMutation:
        """Remove a server ban record by XUID in the given session."""
        result = await session.execute(
            select(Server).filter(Server.server_name == server_name)
        )
        server = result.scalar_one_or_none()
        if not server:
            raise ResourceNotFoundError(f"Server '{server_name}' not found.")

        ban_result = await session.execute(
            select(ServerBan).filter(
                ServerBan.server_id == server.id, ServerBan.xuid == xuid
            )
        )
        ban = ban_result.scalar_one_or_none()

        if not ban:
            raise ResourceNotFoundError(
                f"Ban for '{xuid}' not found on '{server_name}'."
            )

        await session.delete(ban)
        return BanMutation(outcome="removed", message="Ban removed successfully.")

    async def get_bans(self, session: AsyncSession, server_name: str) -> list[BanItem]:
        """Return all bans for a specific server in the given session."""
        result = await session.execute(
            select(Server).filter(Server.server_name == server_name)
        )
        server = result.scalar_one_or_none()
        if not server:
            raise ResourceNotFoundError(f"Server '{server_name}' not found.")

        ban_result = await session.execute(
            select(ServerBan).filter(ServerBan.server_id == server.id)
        )
        bans = ban_result.scalars().all()
        ban_list = [
            BanItem(
                player_name=str(ban.player_name or ""),
                xuid=str(ban.xuid or ""),
                reason=ban.reason,
                banned_at=ban.banned_at.isoformat() if ban.banned_at else None,
            )
            for ban in bans
        ]

        return ban_list
