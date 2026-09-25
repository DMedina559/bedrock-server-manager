"""
Repository for managing Server database entity persistence.
"""

from typing import Any, List, Optional, cast

from sqlalchemy.future import select

from ...state.models import ServerConfigState
from ..models import Server


class ServerRepository:
    """Handles database persistence for server configurations."""

    def __init__(self, db: Any = None):
        self.db = db

    async def get_all_servers(self, session: Any) -> List[ServerConfigState]:
        """Retrieves all servers from the database as ServerConfigState models."""
        result = await session.execute(select(Server))
        servers = []
        for s in result.scalars().all():
            s_name = str(s.server_name)
            custom_dict: dict[str, Any] = (
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
        self, session: Any, server_name: str
    ) -> Optional[Server]:
        """Retrieves a Server SQLAlchemy model record by server_name."""
        result = await session.execute(
            select(Server).filter(Server.server_name == server_name)
        )
        return cast(Optional[Server], result.scalar_one_or_none())

    async def save_server(self, session: Any, cfg: ServerConfigState) -> None:
        """Persists or updates a single ServerConfigState record."""
        server_record: Any = await self.get_server_by_name(session, cfg.server_name)
        if server_record:
            server_record.installed_version = cfg.installed_version
            server_record.status = cfg.status
            server_record.autoupdate = cfg.autoupdate
            server_record.autostart = cfg.autostart
            server_record.target_version = cfg.target_version
            server_record.custom = cfg.custom
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
