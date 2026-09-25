# src/bedrock_server_manager/db/storage.py
"""
Persistence Storage Layer providing state persistence operations between AppState and SQLAlchemy.
"""

import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, AsyncGenerator, Optional

from sqlalchemy.future import select

from ..state.app_state import AppState
from ..state.models import (
    PluginInfoState,
    PluginState,
    ServerConfigState,
    ServerState,
    UserInfoState,
    UserState,
)
from ..state.settings import SettingsState
from .models import Plugin, Server, Setting, User

if TYPE_CHECKING:
    from .database import Database

logger = logging.getLogger(__name__)


class Storage:
    """
    Handles loading, persisting, and transaction boundaries between
    the in-memory AppState and the persistent database.
    """

    def __init__(self, db: "Database", data_dir: Optional[str] = None):
        self.db = db
        self.data_dir = data_dir

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[None, None]:
        """Async context manager for transaction boundaries."""
        async with self.db.session_manager() as session:
            try:
                yield
                await session.commit()
            except Exception as e:
                await session.rollback()
                logger.error(f"Storage transaction failed: {e}")
                raise e

    async def load_state(self, state: Optional[AppState] = None) -> AppState:
        """
        Loads persistent state from the database into the AppState model.
        If no AppState instance is provided, a new one is created.
        """
        if state is None:
            state = AppState()

        # Initialize defaults if data_dir is set
        if self.data_dir:
            state.settings = SettingsState.create_defaults(self.data_dir)

        async with self.db.session_manager() as session:
            result = await session.execute(select(Setting))
            settings_records = result.scalars().all()

            if settings_records:
                user_config = {}
                for record in settings_records:
                    user_config[record.key] = record.value

                state.settings = SettingsState.from_dict(
                    user_config, data_dir=self.data_dir
                )
            else:
                logger.info(
                    "No settings found in database during load_state. Persisting defaults."
                )
                await self._write_settings(session, state.settings)
                await session.commit()

            # Load Servers
            server_result = await session.execute(select(Server))
            for s in server_result.scalars().all():
                cfg = ServerConfigState(
                    server_name=str(s.server_name),
                    installed_version=str(s.installed_version or "UNKNOWN"),
                    status=str(s.status or "UNKNOWN"),
                    autoupdate=bool(s.autoupdate),
                    autostart=bool(s.autostart),
                    target_version=str(s.target_version or "UNKNOWN"),
                    custom=s.custom or {},
                )
                state.servers.servers[s.server_name] = cfg

            # Load Plugins
            plugin_result = await session.execute(select(Plugin))
            for p in plugin_result.scalars().all():
                p_info = PluginInfoState(
                    plugin_name=str(p.plugin_name),
                    enabled=bool(p.enabled),
                    version=str(p.version) if p.version else None,
                    author=str(p.author) if p.author else None,
                    description=str(p.description) if p.description else None,
                    settings=state.settings.plugin_settings.get(str(p.plugin_name), {}),
                )
                state.plugins.plugins[p.plugin_name] = p_info

            # Load Users
            user_result = await session.execute(select(User))
            for u in user_result.scalars().all():
                u_info = UserInfoState(
                    id=int(u.id),
                    username=str(u.username),
                    role=str(u.role),
                    theme=str(u.theme),
                    is_active=bool(u.is_active),
                    full_name=str(u.full_name) if u.full_name else None,
                    email=str(u.email) if u.email else None,
                )
                state.users.users[u.username] = u_info

        state.clear_dirty()
        return state

    async def save_state(self, state: AppState) -> None:
        """Flushes and saves all unpersisted changes from AppState to the database."""
        await self.flush(state)

    async def flush(self, state: AppState) -> None:
        """Flushes modified sub-states in AppState to the database."""
        if not state.is_dirty():
            return

        async with self.db.session_manager() as session:
            if state.settings.is_dirty:
                await self._write_settings(session, state.settings)
            if state.servers.is_dirty:
                await self._write_servers(session, state.servers)
            if state.plugins.is_dirty:
                await self._write_plugins(session, state.plugins)
            if state.users.is_dirty:
                await self._write_users(session, state.users)

            await session.commit()

        state.clear_dirty()

    async def _write_settings(
        self, session: Any, settings_state: SettingsState
    ) -> None:
        """Persists SettingsState dictionary representation into the database Setting table."""
        dict_data = settings_state.to_dict()

        for key, value in dict_data.items():
            result = await session.execute(select(Setting).filter_by(key=key))
            setting = result.scalars().first()
            if setting:
                setting.value = value
            else:
                setting = Setting(key=key, value=value)
                session.add(setting)

    async def _write_servers(self, session: Any, server_state: ServerState) -> None:
        """Persists dirty ServerConfigState objects into the database Server table."""
        for server_name in server_state.dirty_servers:
            cfg = server_state.get(server_name)
            if not cfg:
                continue
            result = await session.execute(
                select(Server).filter_by(server_name=server_name)
            )
            server_record = result.scalars().first()
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

    async def _write_plugins(self, session: Any, plugin_state: PluginState) -> None:
        """Persists dirty PluginInfoState objects into the database Plugin table."""
        for plugin_name in plugin_state.dirty_plugins:
            p_info = plugin_state.get(plugin_name)
            if not p_info:
                continue
            result = await session.execute(
                select(Plugin).filter_by(plugin_name=plugin_name)
            )
            plugin_record = result.scalars().first()
            if plugin_record:
                plugin_record.enabled = p_info.enabled
                plugin_record.version = p_info.version
                plugin_record.author = p_info.author
                plugin_record.description = p_info.description
            else:
                plugin_record = Plugin(
                    plugin_name=p_info.plugin_name,
                    enabled=p_info.enabled,
                    version=p_info.version,
                    author=p_info.author,
                    description=p_info.description,
                )
                session.add(plugin_record)

    async def _write_users(self, session: Any, user_state: UserState) -> None:
        """Persists dirty UserInfoState objects into the database User table."""
        for username in user_state.dirty_users:
            u_info = user_state.get(username)
            if not u_info:
                continue
            result = await session.execute(select(User).filter_by(username=username))
            user_record = result.scalars().first()
            if user_record:
                user_record.role = u_info.role
                user_record.theme = u_info.theme
                user_record.is_active = u_info.is_active
                user_record.full_name = u_info.full_name
                user_record.email = u_info.email
            else:
                user_record = User(
                    username=u_info.username,
                    role=u_info.role,
                    theme=u_info.theme,
                    is_active=u_info.is_active,
                    full_name=u_info.full_name,
                    email=u_info.email,
                )
                session.add(user_record)
