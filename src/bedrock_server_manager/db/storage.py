# src/bedrock_server_manager/db/storage.py
"""
Persistence Storage Layer providing state persistence operations between AppState and SQLAlchemy.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, AsyncGenerator, Callable, List, Optional

from ..error import BSMError, StorageError
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

    def __init__(self, db: "Database", data_dir: str):
        self.db = db
        self.data_dir = data_dir
        self.settings_repo = SettingsRepository(db)
        self.server_repo = ServerRepository(db)
        self.plugin_repo = PluginRepository(db)
        self.user_repo = UserRepository(db)
        self.ban_repo = ServerBanRepository(db)
        self.player_repo = PlayerRepository(db)
        self.audit_log_repo = AuditLogRepository(db)
        self._listeners: List[Callable[[AppState, ChangeSet], Any]] = []
        self._flush_lock = asyncio.Lock()

    def subscribe(self, listener: Callable[[AppState, ChangeSet], Any]) -> None:
        """Registers a callback to receive state change notifications when changesets are persisted."""
        if listener not in self._listeners:
            self._listeners.append(listener)

    def unsubscribe(self, listener: Callable[[AppState, ChangeSet], Any]) -> None:
        """Unregisters a state change listener."""
        if listener in self._listeners:
            self._listeners.remove(listener)

    async def _notify_listeners(self, state: AppState, changeset: ChangeSet) -> None:
        """Invokes registered state change listeners safely."""
        if changeset.is_empty():
            return
        for listener in list(self._listeners):
            try:
                res = listener(state, changeset)
                if asyncio.iscoroutine(res) or asyncio.iscoroutinefunction(listener):
                    await res
            except Exception as e:
                logger.error(
                    f"Error in state change listener {listener}: {e}", exc_info=True
                )

    @asynccontextmanager
    async def transaction(self, max_retries: int = 5) -> AsyncGenerator[Any, None]:
        """Async context manager providing a shared SQLAlchemy session for multi-operation transactions with lock retries."""
        async with self.db.session_manager() as session:
            try:
                yield session
                attempt = 0
                while True:
                    try:
                        await session.commit()
                        break
                    except Exception as commit_err:
                        is_lock_error = (
                            "locked" in str(commit_err).lower()
                            or "busy" in str(commit_err).lower()
                        )
                        if is_lock_error and attempt < max_retries:
                            await session.rollback()
                            attempt += 1
                            logger.warning(
                                f"Database lock during commit, retrying ({attempt}/{max_retries}): {commit_err}"
                            )
                            await asyncio.sleep(0.05 * (2**attempt))
                            continue
                        raise commit_err
            except Exception as e:
                await session.rollback()
                if isinstance(e, BSMError) or e.__class__.__name__ == "HTTPException":
                    raise
                logger.error(f"Storage transaction failed: {e}")
                raise StorageError(f"Database transaction failed: {e}") from e

    async def apply_changeset(self, state: AppState, changeset: ChangeSet) -> None:
        """Applies and persists specific changes recorded in a ChangeSet within a single transaction."""
        if changeset.is_empty():
            return

        async with self._flush_lock:
            async with self.transaction() as session:
                if changeset.settings_changed:
                    async with state.settings.get_lock("global"):
                        settings_snapshot = state.settings.to_dict()
                    await self.settings_repo.save_settings(session, settings_snapshot)
                    async with state.settings.get_lock("global"):
                        if state.settings.to_dict() == settings_snapshot:
                            state.settings.clear_dirty()

                if changeset.servers_changed:
                    for server_name in changeset.servers_changed:
                        async with state.servers.get_lock(server_name):
                            cfg = state.servers.get(server_name)
                        if cfg:
                            await self.server_repo.save_server(session, cfg)
                            async with state.servers.get_lock(server_name):
                                if state.servers.get(server_name) == cfg:
                                    state.servers.remove_dirty_server(server_name)

                if changeset.plugins_changed:
                    for plugin_name in changeset.plugins_changed:
                        async with state.plugins.get_lock(plugin_name):
                            p_info = state.plugins.get(plugin_name)
                        if p_info:
                            await self.plugin_repo.save_plugin(session, p_info)
                            async with state.plugins.get_lock(plugin_name):
                                if state.plugins.get(plugin_name) == p_info:
                                    state.plugins.remove_dirty_plugin(plugin_name)

                if changeset.users_changed:
                    for username in changeset.users_changed:
                        async with state.users.get_lock(username):
                            u_info = state.users.get(username)
                        if u_info:
                            await self.user_repo.save_user(session, u_info)
                            async with state.users.get_lock(username):
                                if state.users.get(username) == u_info:
                                    state.users.remove_dirty_user(username)

            # Listener notifications run strictly post-commit outside the transaction boundary
            await self._notify_listeners(state, changeset)

    async def load_state(self, state: Optional[AppState] = None) -> AppState:
        """
        Loads persistent state from the database into the AppState model.
        If no AppState instance is provided, a new one is created.
        """
        if state is None:
            state = AppState()

        async with self.db.session_manager() as session:
            settings_dict = await self.settings_repo.get_all_settings(session)
            if settings_dict:
                state.settings = SettingsState.from_dict(
                    settings_dict, data_dir=self.data_dir
                )
            else:
                state.settings = SettingsState.create_defaults(self.data_dir)
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

    async def save_players(self, players_data: list) -> int:
        """Saves player data to the database via player repository within a transaction."""
        async with self.transaction() as session:
            res = await self.player_repo.save_players(session, players_data)
            return int(res)

    async def get_all_players(self) -> list:
        """Retrieves all known players from the database via player repository within a transaction."""
        async with self.transaction() as session:
            res = await self.player_repo.get_all_players(session)
            return list(res)

    async def save_state(self, state: AppState) -> None:
        """Flushes and saves all unpersisted changes from AppState to the database."""
        await self.flush(state)

    async def flush(self, state: AppState) -> None:
        """Flushes modified sub-states in AppState to the database."""
        if not state.is_dirty():
            return

        async with self._flush_lock:
            if not state.is_dirty():
                return

            flushed_changeset = ChangeSet()
            if state.settings.is_dirty:
                flushed_changeset.add_setting("global")
            for s in state.servers.dirty_servers:
                flushed_changeset.add_server(s)
            for p in state.plugins.dirty_plugins:
                flushed_changeset.add_plugin(p)
            for u in state.users.dirty_users:
                flushed_changeset.add_user(u)

            async with self.transaction() as session:
                if state.settings.is_dirty:
                    async with state.settings.get_lock("global"):
                        settings_snapshot = state.settings.to_dict()
                    await self.settings_repo.save_settings(session, settings_snapshot)
                    async with state.settings.get_lock("global"):
                        if state.settings.to_dict() == settings_snapshot:
                            state.settings.clear_dirty()

                if state.servers.is_dirty:
                    for server_name in list(state.servers.dirty_servers):
                        async with state.servers.get_lock(server_name):
                            cfg = state.servers.get(server_name)
                        if cfg:
                            await self.server_repo.save_server(session, cfg)
                            async with state.servers.get_lock(server_name):
                                if state.servers.get(server_name) == cfg:
                                    state.servers.remove_dirty_server(server_name)

                if state.plugins.is_dirty:
                    for plugin_name in list(state.plugins.dirty_plugins):
                        async with state.plugins.get_lock(plugin_name):
                            p_info = state.plugins.get(plugin_name)
                        if p_info:
                            await self.plugin_repo.save_plugin(session, p_info)
                            async with state.plugins.get_lock(plugin_name):
                                if state.plugins.get(plugin_name) == p_info:
                                    state.plugins.remove_dirty_plugin(plugin_name)

                if state.users.is_dirty:
                    for username in list(state.users.dirty_users):
                        async with state.users.get_lock(username):
                            u_info = state.users.get(username)
                        if u_info:
                            await self.user_repo.save_user(session, u_info)
                            async with state.users.get_lock(username):
                                if state.users.get(username) == u_info:
                                    state.users.remove_dirty_user(username)

            # Listener notifications run strictly post-commit outside the transaction boundary
            await self._notify_listeners(state, flushed_changeset)
