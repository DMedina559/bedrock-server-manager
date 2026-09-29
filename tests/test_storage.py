# tests/test_storage.py
"""
Integration and unit tests for the Storage layer.
"""

import os

import pytest

from bedrock_server_manager.db.storage import Storage
from bedrock_server_manager.state import (
    AppState,
    PluginInfoState,
    ServerConfigState,
)


@pytest.mark.asyncio
async def test_storage_load_and_flush(db):
    test_data_dir = "/tmp/test_storage_data"
    storage = Storage(db=db, data_dir=test_data_dir)
    state = AppState()

    # Load initial state into state
    await storage.load_state(state)
    assert state.settings.paths.servers == os.path.join(test_data_dir, "servers")
    assert not state.is_dirty()

    # Modify setting
    state.settings.set("retention.backups", 10)
    assert state.is_dirty()

    # Flush changes to DB
    await storage.flush(state)
    assert not state.is_dirty()

    # Reload into new state model to verify persistence
    new_state = AppState()
    await storage.load_state(new_state)
    assert new_state.settings.retention.backups == 10


@pytest.mark.asyncio
async def test_storage_transaction(db):
    storage = Storage(db=db, data_dir="/tmp/test_storage_tx")
    state = AppState()
    await storage.load_state(state)

    async with storage.transaction():
        state.settings.set("web.port", 9999)
        await storage.flush(state)

    # Verify reload
    reloaded = AppState()
    await storage.load_state(reloaded)
    assert reloaded.settings.web.port == 9999


@pytest.mark.asyncio
async def test_storage_server_persistence(db):
    storage = Storage(db=db, data_dir="/tmp/test_storage_server")
    state = AppState()
    await storage.load_state(state)

    srv = ServerConfigState(
        server_name="lobby",
        installed_version="1.21.0.03",
        status="RUNNING",
        autostart=True,
        custom={"motd": "Welcome!"},
    )
    state.servers.set(srv)
    assert state.is_dirty()

    await storage.flush(state)
    assert not state.is_dirty()

    # Verify reloading server state from DB
    reloaded_state = AppState()
    await storage.load_state(reloaded_state)

    loaded_srv = reloaded_state.servers.get("lobby")
    assert loaded_srv is not None
    assert loaded_srv.installed_version == "1.21.0.03"
    assert loaded_srv.status == "RUNNING"
    assert loaded_srv.autostart is True
    assert loaded_srv.custom == {"motd": "Welcome!"}


@pytest.mark.asyncio
async def test_storage_plugin_and_user_persistence(db, test_admin_user):
    storage = Storage(db=db, data_dir="/tmp/test_storage_plugin_user")
    state = AppState()
    await storage.load_state(state)

    # Verify user loaded from database
    admin_user = state.users.get("adminuser")
    assert admin_user is not None
    assert admin_user.role == "admin"

    # Modify user theme
    admin_user.theme = "nord"
    state.users.set(admin_user)

    # Add plugin state
    plugin = PluginInfoState(
        plugin_name="discord_bridge",
        enabled=True,
        version="2.1.0",
        author="BSM",
        description="Discord bot bridge",
    )
    state.plugins.set(plugin)

    await storage.flush(state)

    # Reload into new state
    reloaded = AppState()
    await storage.load_state(reloaded)

    reloaded_admin = reloaded.users.get("adminuser")
    assert reloaded_admin is not None
    assert reloaded_admin.theme == "nord"

    reloaded_plugin = reloaded.plugins.get("discord_bridge")
    assert reloaded_plugin is not None
    assert reloaded_plugin.enabled is True
    assert reloaded_plugin.version == "2.1.0"


@pytest.mark.asyncio
async def test_storage_subscription_observer(db):
    storage = Storage(db=db, data_dir="/tmp/test_storage_sub")
    state = AppState()
    await storage.load_state(state)

    notified_changes = []

    async def on_change(app_st, changeset):
        notified_changes.append(changeset)

    storage.subscribe(on_change)

    # Modify state via changeset
    state.settings.set("retention.downloads", 5)
    await storage.flush(state)

    assert len(notified_changes) == 1
    assert notified_changes[0].settings_changed

    # Unsubscribe
    storage.unsubscribe(on_change)
    state.settings.set("retention.downloads", 7)
    await storage.flush(state)

    assert len(notified_changes) == 1


@pytest.mark.asyncio
async def test_alembic_migrations_upgrade_and_downgrade(tmp_path):
    from bedrock_server_manager.db.database import Database
    from bedrock_server_manager.utils.migration import (
        run_migrations_downgrade,
        run_migrations_upgrade,
    )

    db_path = tmp_path / "migration_test.db"
    db = Database(f"sqlite:///{db_path}")

    # Upgrade from empty database to head via Alembic
    await run_migrations_upgrade(db)

    # Downgrade 1 revision and upgrade back to head
    await run_migrations_downgrade(db, "-1")
    await run_migrations_upgrade(db)

    await db.shutdown()
