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
    TypeVar,
)

from pydantic import BaseModel
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from ..error import BSMError, StorageError
from ..state.app_state import AppState
from ..state.changeset import ChangeSet
from ..state.settings import SettingsState
from ..state.validation import json_equal
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

Record = TypeVar("Record", bound=BaseModel)

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

    @property
    def write_lock(self) -> asyncio.Lock:
        """Serialize domain transactions with state flushes and reloads."""
        return self._flush_lock

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
            settings_snapshot = None
            async with self.transaction() as session:
                if changeset.settings_changed:
                    async with state.settings.get_lock("global"):
                        settings_snapshot = state.settings.to_dict()
                    await self.settings_repo.save_settings(session, settings_snapshot)
                server_snapshots = await self._save_records(
                    session,
                    changeset.servers_changed,
                    state.servers.get_lock,
                    state.servers.get,
                    self.server_repo.save_server,
                )
                plugin_snapshots = await self._save_records(
                    session,
                    changeset.plugins_changed,
                    state.plugins.get_lock,
                    state.plugins.get,
                    self.plugin_repo.save_plugin,
                )
                user_snapshots = await self._save_records(
                    session,
                    changeset.users_changed,
                    state.users.get_lock,
                    state.users.get,
                    self.user_repo.save_user,
                )
            # The transaction has committed. Failed commits never acknowledge dirtiness.
            if settings_snapshot is not None:
                async with state.settings.get_lock("global"):
                    if json_equal(state.settings.to_dict(), settings_snapshot):
                        state.settings.clear_dirty()
            await self._acknowledge_records(
                server_snapshots,
                state.servers.get_lock,
                state.servers.get,
                state.servers.remove_dirty_server,
            )
            await self._acknowledge_records(
                plugin_snapshots,
                state.plugins.get_lock,
                state.plugins.get,
                state.plugins.remove_dirty_plugin,
            )
            await self._acknowledge_records(
                user_snapshots,
                state.users.get_lock,
                state.users.get,
                state.users.remove_dirty_user,
            )
        # Listeners may initiate another write; never invoke them under the flush lock.
        await self._notify_listeners(state, changeset)

    @staticmethod
    async def _save_records(
        session: AsyncSession,
        names: set[str],
        get_lock: Callable[[str], asyncio.Lock],
        get: Callable[[str], Record | None],
        save: Callable[[AsyncSession, Record], Awaitable[None]],
    ) -> list[tuple[str, Record]]:
        snapshots = []
        for name in names:
            async with get_lock(name):
                snapshot = get(name)
            if snapshot is not None:
                snapshot = type(snapshot).model_validate(snapshot)
                await save(session, snapshot)
                snapshots.append((name, snapshot))
        return snapshots

    @staticmethod
    async def _acknowledge_records(
        snapshots: list[tuple[str, Record]],
        get_lock: Callable[[str], asyncio.Lock],
        get: Callable[[str], Record | None],
        remove_dirty: Callable[[str], None],
    ) -> None:
        for name, snapshot in snapshots:
            async with get_lock(name):
                current = get(name)
                if current is not None and json_equal(
                    current.model_dump(mode="json"), snapshot.model_dump(mode="json")
                ):
                    remove_dirty(name)

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
            state.servers.replace_loaded(loaded_servers)
            state.plugins.replace_loaded(loaded_plugins)
            state.users.replace_loaded(loaded_users)
        return state

    async def save_players(self, players_data: list[dict[str, str]]) -> int:
        """Saves player data to the database via player repository within a transaction."""
        async with self.transaction() as session:
            res = await self.player_repo.save_players(session, players_data)
            return int(res)

    async def get_all_players(self) -> list[dict[str, str]]:
        """Retrieves all known players from the database via player repository within a transaction."""
        async with self.transaction() as session:
            res = await self.player_repo.get_all_players(session)
            return list(res)

    async def save_state(self, state: AppState) -> None:
        """Flushes and saves all unpersisted changes from AppState to the database."""
        await self.flush(state)

    async def delete_server(self, state: AppState, server_name: str) -> None:
        """Serialize deletion with reload/flush and acknowledge only after commit."""
        async with self._flush_lock:
            async with state.servers.get_lock(server_name):
                async with self.transaction() as session:
                    await self.server_repo.delete_server(session, server_name)
                state.servers.remove(server_name)

    async def flush(self, state: AppState) -> None:
        """Persist pending entity snapshots through the same commit boundary."""
        changeset = ChangeSet()
        if state.settings.is_dirty:
            changeset.add_setting("global")
        changeset.servers_changed.update(state.servers.dirty_servers)
        changeset.plugins_changed.update(state.plugins.dirty_plugins)
        changeset.users_changed.update(state.users.dirty_users)
        await self.apply_changeset(state, changeset)
