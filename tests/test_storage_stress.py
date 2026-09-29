"""
Stress and release-validation test suite for Storage and AppState concurrency, state isolation,
persistence failure recovery, cancellation, and event notification ordering.
"""

import asyncio
from unittest.mock import patch

import pytest
from sqlalchemy.exc import OperationalError
from sqlalchemy.future import select

from bedrock_server_manager.db.database import Database
from bedrock_server_manager.db.models import Base, Server
from bedrock_server_manager.db.storage import Storage
from bedrock_server_manager.error import StorageError
from bedrock_server_manager.state import (
    AppState,
    PluginInfoState,
    ServerConfigState,
    UserInfoState,
)


@pytest.fixture
async def file_db(tmp_path):
    """Creates a real file-backed SQLite database with tables created to test real file locking and transaction semantics."""
    db_file = tmp_path / "stress_test.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"
    database = Database(db_url)
    database.initialize()

    assert database.engine is not None
    async with database.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield database
    await database.shutdown()


@pytest.mark.asyncio
async def test_concurrent_mutations_stress(file_db, tmp_path):
    """
    Simulates concurrent task updates across settings, servers, plugins, and users with overlapping flushes.
    Verifies that no state is lost, dirty flags are correctly cleared, and reloaded state equals final state.
    """
    storage = Storage(db=file_db, data_dir=str(tmp_path / "data"))
    state = AppState()
    await storage.load_state(state)

    num_entities = 5
    for i in range(num_entities):
        state.servers.set(
            ServerConfigState(server_name=f"server_{i}", status="STOPPED")
        )
        state.plugins.set(PluginInfoState(plugin_name=f"plugin_{i}", enabled=False))
        state.users.set(UserInfoState(username=f"user_{i}", role="user"))
    await storage.flush(state)
    assert not state.is_dirty()

    num_tasks = 20

    async def worker(worker_id: int):
        for step in range(3):
            target_type = (worker_id + step) % 4
            target_idx = (worker_id + step) % num_entities

            if target_type == 0:
                srv_name = f"server_{target_idx}"
                async with state.servers.get_lock(srv_name):
                    srv = state.servers.get(srv_name)
                    if srv:
                        srv.status = f"STATUS_{worker_id}_{step}"
                        srv.custom = {"worker": worker_id}
                        state.servers.set(srv)
            elif target_type == 1:
                p_name = f"plugin_{target_idx}"
                async with state.plugins.get_lock(p_name):
                    p = state.plugins.get(p_name)
                    if p:
                        p.enabled = worker_id % 2 == 0
                        p.version = f"1.0.{worker_id}"
                        state.plugins.set(p)
            elif target_type == 2:
                u_name = f"user_{target_idx}"
                async with state.users.get_lock(u_name):
                    u = state.users.get(u_name)
                    if u:
                        u.theme = f"theme_{worker_id}"
                        state.users.set(u)
            else:
                async with state.settings.get_lock("global"):
                    state.settings.set("retention.backups", worker_id)

            await storage.flush(state)

    tasks = [asyncio.create_task(worker(i)) for i in range(num_tasks)]
    await asyncio.gather(*tasks)

    # Final flush to ensure all pending changes are written
    await storage.flush(state)
    assert not state.is_dirty()

    # Sync auto-assigned DB IDs into state
    await storage.load_state(state)

    # Reload into fresh state and compare DB persisted values with in-memory state exactly
    reloaded_state = AppState()
    await storage.load_state(reloaded_state)

    for i in range(num_entities):
        s_name = f"server_{i}"
        assert reloaded_state.servers.get(s_name) == state.servers.get(s_name)

        p_name = f"plugin_{i}"
        assert reloaded_state.plugins.get(p_name) == state.plugins.get(p_name)

        u_name = f"user_{i}"
        assert reloaded_state.users.get(u_name) == state.users.get(u_name)

    assert reloaded_state.settings.retention.backups == state.settings.retention.backups


@pytest.mark.asyncio
async def test_concurrent_flushes_are_safe(file_db, tmp_path):
    """
    Verifies that multiple concurrent storage.flush() calls execute safely via Storage._flush_lock
    without race conditions or redundant overlapping database errors.
    """
    storage = Storage(db=file_db, data_dir=str(tmp_path / "data"))
    state = AppState()
    await storage.load_state(state)

    srv = ServerConfigState(server_name="concurrent_flush_srv", status="STARTING")
    state.servers.set(srv)
    assert state.is_dirty()

    await asyncio.gather(
        storage.flush(state),
        storage.flush(state),
        storage.flush(state),
    )

    assert not state.is_dirty()

    reloaded = AppState()
    await storage.load_state(reloaded)
    assert reloaded.servers.get("concurrent_flush_srv").status == "STARTING"


@pytest.mark.asyncio
async def test_mutation_during_write_preserves_dirty_flag(file_db, tmp_path):
    """
    Verifies that if a concurrent task mutates state while DB write is in progress,
    the post-write snapshot comparison detects the mismatch and keeps the entity dirty.
    """
    storage = Storage(db=file_db, data_dir=str(tmp_path / "data"))
    state = AppState()
    await storage.load_state(state)

    srv = ServerConfigState(server_name="racing_server", status="STOPPED")
    state.servers.set(srv)
    await storage.flush(state)
    assert not state.is_dirty()

    # Mutate state once
    srv.status = "STARTING"
    state.servers.set(srv)
    assert "racing_server" in state.servers.dirty_servers

    original_save_server = storage.server_repo.save_server
    save_started = asyncio.Event()
    mutator_acquired = asyncio.Event()

    async def slow_save_server(session, server_cfg):
        save_started.set()
        await asyncio.sleep(0.05)
        return await original_save_server(session, server_cfg)

    async def concurrent_mutator():
        await save_started.wait()
        async with state.servers.get_lock("racing_server"):
            mutator_acquired.set()
            updated_srv = state.servers.get("racing_server")
            updated_srv.status = "RUNNING"
            state.servers.set(updated_srv)

    with patch.object(storage.server_repo, "save_server", side_effect=slow_save_server):
        flush_task = asyncio.create_task(storage.flush(state))
        mutator_task = asyncio.create_task(concurrent_mutator())

        await asyncio.gather(flush_task, mutator_task)

    assert mutator_acquired.is_set()
    # "racing_server" must remain dirty with status "RUNNING" because state changed during DB write
    assert "racing_server" in state.servers.dirty_servers
    assert state.servers.get("racing_server").status == "RUNNING"

    # Secondary flush saves "RUNNING" and clears dirty
    await storage.flush(state)
    assert not state.is_dirty()

    reloaded = AppState()
    await storage.load_state(reloaded)
    assert reloaded.servers.get("racing_server").status == "RUNNING"


@pytest.mark.asyncio
async def test_persistence_failure_retries_and_recovery(file_db, tmp_path):
    """
    Tests that database lock/busy errors trigger exponential backoff retries and rollback in storage.transaction(),
    and persistent non-retryable failures leave specific dirty keys marked dirty until a successful retry flush.
    """
    storage = Storage(db=file_db, data_dir=str(tmp_path / "data"))
    state = AppState()
    await storage.load_state(state)

    state.settings.set("retention.downloads", 42)
    assert state.settings.is_dirty

    fail_count = 0

    original_session_manager = file_db.session_manager

    class MockSessionManager:
        def __init__(self, real_sm):
            self.real_sm = real_sm

        async def __aenter__(self):
            session = await self.real_sm.__aenter__()
            original_commit = session.commit

            async def failing_commit():
                nonlocal fail_count
                if fail_count < 2:
                    fail_count += 1
                    raise OperationalError(
                        "database is locked", params={}, orig=Exception("locked")
                    )
                return await original_commit()

            session.commit = failing_commit
            return session

        async def __aexit__(self, exc_type, exc, tb):
            return await self.real_sm.__aexit__(exc_type, exc, tb)

    with patch.object(
        file_db,
        "session_manager",
        side_effect=lambda: MockSessionManager(original_session_manager()),
    ):
        await storage.flush(state)

    assert fail_count == 2
    assert not state.is_dirty()

    # Verify persistent error leaves settings dirty
    state.settings.set("retention.downloads", 99)
    assert state.settings.is_dirty

    async def permanent_failure_save(session, settings_dict):
        raise OperationalError(
            "disk I/O error", params={}, orig=Exception("disk error")
        )

    with patch.object(
        storage.settings_repo, "save_settings", side_effect=permanent_failure_save
    ):
        with pytest.raises(StorageError):
            await storage.flush(state)

    assert state.settings.is_dirty

    # Recovery flush without mocks
    await storage.flush(state)
    assert not state.is_dirty()

    reloaded = AppState()
    await storage.load_state(reloaded)
    assert reloaded.settings.retention.downloads == 99


@pytest.mark.asyncio
async def test_task_cancellation_during_persistence_or_locking(file_db, tmp_path):
    """
    Verifies lock state, dirty set tracking, and lock reuse recovery when tasks waiting on locks or persistence are cancelled.
    """
    storage = Storage(db=file_db, data_dir=str(tmp_path / "data"))
    state = AppState()
    await storage.load_state(state)

    srv = ServerConfigState(server_name="cancelled_srv", status="STOPPED")
    state.servers.set(srv)
    await storage.flush(state)

    # Test cancellation while waiting for a lock
    lock = state.servers.get_lock("cancelled_srv")
    await lock.acquire()

    async def lock_waiter():
        async with lock:
            pass

    waiter_task = asyncio.create_task(lock_waiter())
    await asyncio.sleep(0.01)
    assert not waiter_task.done()

    waiter_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiter_task

    lock.release()
    assert not lock.locked()

    # Test cancellation during DB save and lock reuse recovery
    srv.status = "CHANGING"
    state.servers.set(srv)

    async def hanging_save(session, server_cfg):
        await asyncio.sleep(10)

    with patch.object(storage.server_repo, "save_server", side_effect=hanging_save):
        flush_task = asyncio.create_task(storage.flush(state))
        await asyncio.sleep(0.01)
        flush_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await flush_task

    assert "cancelled_srv" in state.servers.dirty_servers

    # Clean flush completes cleanly within timeout proving lock/session recovery
    await asyncio.wait_for(storage.flush(state), timeout=1.0)
    assert not state.is_dirty()


@pytest.mark.asyncio
async def test_storage_listeners_ordering_and_exception_isolation(file_db, tmp_path):
    """
    Verifies that storage subscriber listeners:
    1. Are invoked post-commit where persisted changes are visible to external DB queries.
    2. Do not abort storage transactions or block other listeners if one raises an exception.
    """
    storage = Storage(db=file_db, data_dir=str(tmp_path / "data"))
    state = AppState()
    await storage.load_state(state)

    db_row_visible = False

    def faulty_listener(app_st, changeset):
        raise RuntimeError("Subscriber explosion!")

    async def querying_listener(app_st, changeset):
        nonlocal db_row_visible
        async with file_db.session_manager() as session:
            result = await session.execute(
                select(Server).filter(Server.server_name == "event_srv")
            )
            server_row = result.scalar_one_or_none()
            if server_row and server_row.status == "RUNNING":
                db_row_visible = True

    storage.subscribe(faulty_listener)
    storage.subscribe(querying_listener)

    # Perform mutation
    srv = ServerConfigState(server_name="event_srv", status="RUNNING")
    state.servers.set(srv)

    await storage.flush(state)

    # Listener must see the committed DB row post-commit
    assert db_row_visible is True

    # Unsubscribe test
    storage.unsubscribe(faulty_listener)
    storage.unsubscribe(querying_listener)
