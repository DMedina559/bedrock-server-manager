# src/bedrock_server_manager/db/storage.py
"""
Persistence Storage Layer providing state persistence operations between AppState and SQLAlchemy.
"""

import asyncio
import inspect
import logging
from contextlib import asynccontextmanager
from copy import deepcopy
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncGenerator,
    Awaitable,
    Callable,
    List,
    Optional,
)

from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

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
                res = listener(state, deepcopy(changeset))
                if inspect.isawaitable(res):
                    await res
            except Exception as e:
                logger.error(
                    f"Error in state change listener {listener}: {e}", exc_info=True
                )

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[AsyncSession, None]:
        """Commit once; a rolled-back unit of work must be replayed by its caller."""
        async with self.db.session_manager() as session:
            try:
                yield session
                await session.commit()
            except BaseException as error:
                await session.rollback()
                if (
                    isinstance(error, (BSMError, asyncio.CancelledError))
                    or error.__class__.__name__ == "HTTPException"
                ):
                    raise
                if not isinstance(error, Exception):
                    raise
                raise StorageError("Database transaction failed.") from error

    async def apply_changeset(self, state: AppState, changeset: ChangeSet) -> None:
        """Retry the complete unit of work, never a commit after a rollback."""
        for attempt in range(6):
            try:
                await self._apply_changeset_once(state, changeset)
                return
            except StorageError as error:
                cause = error.__cause__
                locked = isinstance(cause, OperationalError) and any(
                    word in str(cause.orig).lower() for word in ("locked", "busy")
                )
                if not locked or attempt == 5:
                    raise
                await asyncio.sleep(0.05 * (2**attempt))

    async def _apply_changeset_once(
        self, state: AppState, changeset: ChangeSet
    ) -> None:
        """Persist snapshots, then acknowledge only the versions actually committed."""
        changeset = deepcopy(changeset)
        if changeset.is_empty():
            return
        async with self._flush_lock:
            snapshots: list[tuple[Any, str, Any]] = []
            settings_snapshot = None
            async with self.transaction() as session:
                if changeset.settings_changed:
                    async with state.settings.get_lock("global"):
                        settings_snapshot = state.settings.to_dict()
                    await self.settings_repo.save_settings(session, settings_snapshot)
                groups: list[tuple[Any, set[str], Callable[..., Awaitable[None]]]] = [
                    (
                        state.servers,
                        changeset.servers_changed,
                        self.server_repo.save_server,
                    ),
                    (
                        state.plugins,
                        changeset.plugins_changed,
                        self.plugin_repo.save_plugin,
                    ),
                    (state.users, changeset.users_changed, self.user_repo.save_user),
                ]
                for domain, names, save in groups:
                    for name in names:
                        async with domain.get_lock(name):
                            snapshot = domain.get(name)
                        if snapshot is not None:
                            await save(session, snapshot)
                            snapshots.append((domain, name, snapshot))
            # The transaction has committed. Failed commits never acknowledge dirtiness.
            if settings_snapshot is not None:
                async with state.settings.get_lock("global"):
                    if state.settings.to_dict() == settings_snapshot:
                        state.settings.clear_dirty()
            for domain, name, snapshot in snapshots:
                async with domain.get_lock(name):
                    if domain.get(name) == snapshot:
                        if domain is state.servers:
                            domain.remove_dirty_server(name)
                        elif domain is state.plugins:
                            domain.remove_dirty_plugin(name)
                        else:
                            domain.remove_dirty_user(name)
        # Listeners may initiate another write; never invoke them under the flush lock.
        await self._notify_listeners(state, changeset)

    async def load_state(self, state: Optional[AppState] = None) -> AppState:
        """
        Loads persistent state from the database into the AppState model.
        If no AppState instance is provided, a new one is created.
        """
        if state is None:
            state = AppState()

        async with self._flush_lock:
            return await self._load_state(state)

    async def _load_state(self, state: AppState) -> AppState:
        async with self.db.session_manager() as session:
            settings_dict = await self.settings_repo.get_all_settings(session)
            if settings_dict:
                loaded_settings = SettingsState.from_dict(
                    settings_dict, data_dir=self.data_dir
                )
            else:
                loaded_settings = SettingsState.create_defaults(self.data_dir)
                logger.info(
                    "No settings found in database during load_state. Persisting defaults."
                )
                await self.settings_repo.save_settings(
                    session, loaded_settings.to_dict()
                )
                await session.commit()

            servers = await self.server_repo.get_all_servers(session)
            plugins = await self.plugin_repo.get_all_plugins(session)
            users = await self.user_repo.get_all_users(session)

        async with state.lock:
            # Mutations made while reads were pending must survive a reload.
            if not state.settings.is_dirty:
                state.settings = loaded_settings
            loaded_servers = {item.server_name: item for item in servers}
            loaded_plugins = {item.plugin_name: item for item in plugins}
            loaded_users = {item.username: item for item in users}
            loaded_servers.update(
                {
                    name: state.servers.servers[name]
                    for name in state.servers.dirty_servers
                    if name in state.servers.servers
                }
            )
            loaded_plugins.update(
                {
                    name: state.plugins.plugins[name]
                    for name in state.plugins.dirty_plugins
                    if name in state.plugins.plugins
                }
            )
            loaded_users.update(
                {
                    name: state.users.users[name]
                    for name in state.users.dirty_users
                    if name in state.users.users
                }
            )
            state.servers.servers = loaded_servers
            state.plugins.plugins = loaded_plugins
            state.users.users = loaded_users
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
        """Persist pending entity snapshots through the same commit boundary."""
        changeset = ChangeSet()
        if state.settings.is_dirty:
            changeset.add_setting("global")
        changeset.servers_changed.update(state.servers.dirty_servers)
        changeset.plugins_changed.update(state.plugins.dirty_plugins)
        changeset.users_changed.update(state.users.dirty_users)
        await self.apply_changeset(state, changeset)
