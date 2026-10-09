"""
Repository for managing Server database entity persistence.
"""

from typing import List, Optional, cast

from pydantic import JsonValue
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm.attributes import flag_modified

from ...state.models import ServerConfigState
from ...state.validation import json_equal
from ..database import Database
from ..models import Server, ServerBan


class ServerRepository:
    """Handles database persistence for server configurations."""

    def __init__(self, db: Database | None = None):
        self.db = db

    async def get_all_servers(self, session: AsyncSession) -> List[ServerConfigState]:
        """Retrieves all servers from the database as ServerConfigState models."""
        result = await session.execute(select(Server))
        servers = []
        for s in result.scalars().all():
            s_name = str(s.server_name)
            custom_dict: dict[str, JsonValue] = (
                dict(s.custom) if isinstance(s.custom, dict) else {}
            )
            cfg = ServerConfigState(
                server_name=s_name,
                installed_version=str(s.installed_version or "UNKNOWN"),
                status=str(s.status or "UNKNOWN"),
                autoupdate=bool(s.autoupdate),
                autostart=bool(s.autostart),
                target_version=str(s.target_version or "UNKNOWN"),
                custom=custom_dict,
            )
            servers.append(cfg)
        return servers

    async def get_server_by_name(
        self, session: AsyncSession, server_name: str
    ) -> Optional[Server]:
        """Retrieves a Server SQLAlchemy model record by server_name."""
        result = await session.execute(
            select(Server).filter(Server.server_name == server_name)
        )
        return cast(Optional[Server], result.scalar_one_or_none())

    async def save_server(self, session: AsyncSession, cfg: ServerConfigState) -> None:
        """Persists or updates a single ServerConfigState record."""
        server_record = await self.get_server_by_name(session, cfg.server_name)
        if server_record:
            server_record.installed_version = cfg.installed_version
            server_record.status = cfg.status
            server_record.autoupdate = cfg.autoupdate
            server_record.autostart = cfg.autostart
            server_record.target_version = cfg.target_version
            if not json_equal(server_record.custom, cfg.custom):
                server_record.custom = cfg.custom
                flag_modified(server_record, "custom")
        else:
            server_record = Server(
                server_name=cfg.server_name,
                installed_version=cfg.installed_version,
                status=cfg.status,
                autoupdate=cfg.autoupdate,
                autostart=cfg.autostart,
                target_version=cfg.target_version,
                custom=cfg.custom,
            )
            session.add(server_record)

    async def delete_server(self, session: AsyncSession, server_name: str) -> bool:
        """Deletes a server record and its associated bans from the database."""
        db_server = await self.get_server_by_name(session, server_name)
        if db_server:
            await session.execute(
                delete(ServerBan).filter(ServerBan.server_id == db_server.id)
            )
            await session.delete(db_server)
            return True
        return False
