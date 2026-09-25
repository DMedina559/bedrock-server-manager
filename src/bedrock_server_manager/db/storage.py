# src/bedrock_server_manager/db/storage.py
"""
Persistence Storage Layer providing state persistence operations between AppState and SQLAlchemy.
"""

import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, AsyncGenerator, Optional

from ..state.app_state import AppState
from ..state.changeset import ChangeSet
from ..state.settings import SettingsState
from .repositories import (
    AuditLogRepository,
    PlayerRepository,
    PluginRepository,
    ServerBanRepository,
    ServerRepository,
    SettingsRepository,
    UserRepository,
)

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
        self.settings_repo = SettingsRepository(db)
        self.server_repo = ServerRepository(db)
        self.plugin_repo = PluginRepository(db)
        self.user_repo = UserRepository(db)
        self.ban_repo = ServerBanRepository(db)
        self.player_repo = PlayerRepository(db)
        self.audit_log_repo = AuditLogRepository(db)

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[Any, None]:
        """Async context manager providing a shared SQLAlchemy session for multi-operation transactions."""
        async with self.db.session_manager() as session:
            try:
                yield session
                await session.commit()
            except Exception as e:
                await session.rollback()
                logger.error(f"Storage transaction failed: {e}")
                raise e

    async def apply_changeset(self, state: AppState, changeset: ChangeSet) -> None:
        """Applies and persists specific changes recorded in a ChangeSet within a single transaction."""
        if changeset.is_empty():
            return

        async with self.transaction() as session:
            if changeset.settings_changed:
                await self.settings_repo.save_settings(
                    session, state.settings.to_dict()
                )
            if changeset.servers_changed:
                for server_name in changeset.servers_changed:
                    cfg = state.servers.get(server_name)
                    if cfg:
                        await self.server_repo.save_server(session, cfg)
            if changeset.plugins_changed:
                for plugin_name in changeset.plugins_changed:
                    p_info = state.plugins.get(plugin_name)
                    if p_info:
                        await self.plugin_repo.save_plugin(session, p_info)
            if changeset.users_changed:
                for username in changeset.users_changed:
                    u_info = state.users.get(username)
                    if u_info:
                        await self.user_repo.save_user(session, u_info)

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
            settings_dict = await self.settings_repo.get_all_settings(session)
            if settings_dict:
                state.settings = SettingsState.from_dict(
                    settings_dict, data_dir=self.data_dir
                )
            else:
                logger.info(
                    "No settings found in database during load_state. Persisting defaults."
                )
                await self.settings_repo.save_settings(
                    session, state.settings.to_dict()
                )
                await session.commit()

            # Load Servers
            servers = await self.server_repo.get_all_servers(session)
            for cfg in servers:
                state.servers.servers[cfg.server_name] = cfg

            # Load Plugins
            plugins = await self.plugin_repo.get_all_plugins(
                session, plugin_settings_map=state.settings.plugin_settings
            )
            for p_info in plugins:
                state.plugins.plugins[p_info.plugin_name] = p_info

            # Load Users
            users = await self.user_repo.get_all_users(session)
            for u_info in users:
                state.users.users[u_info.username] = u_info

        state.clear_dirty()
        return state

    async def save_state(self, state: AppState) -> None:
        """Flushes and saves all unpersisted changes from AppState to the database."""
        await self.flush(state)

    async def flush(self, state: AppState) -> None:
        """Flushes modified sub-states in AppState to the database."""
        if not state.is_dirty():
            return

        async with self.transaction() as session:
            if state.settings.is_dirty:
                await self.settings_repo.save_settings(
                    session, state.settings.to_dict()
                )
            if state.servers.is_dirty:
                for server_name in state.servers.dirty_servers:
                    cfg = state.servers.get(server_name)
                    if cfg:
                        await self.server_repo.save_server(session, cfg)
            if state.plugins.is_dirty:
                for plugin_name in state.plugins.dirty_plugins:
                    p_info = state.plugins.get(plugin_name)
                    if p_info:
                        await self.plugin_repo.save_plugin(session, p_info)
            if state.users.is_dirty:
                for username in state.users.dirty_users:
                    u_info = state.users.get(username)
                    if u_info:
                        await self.user_repo.save_user(session, u_info)

        state.clear_dirty()
