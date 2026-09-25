# tests/test_storage.py
"""
Integration and unit tests for the Storage layer.
"""

import pytest

from bedrock_server_manager.db.storage import Storage
from bedrock_server_manager.state import (
    AppState,
    PluginInfoState,
    ServerConfigState,
)


@pytest.mark.asyncio
async def test_storage_load_and_flush(db):
    storage = Storage(db=db, data_dir="/tmp/test_storage_data")
    state = AppState()

    # Load initial state into state
    await storage.load_state(state)
    assert state.settings.paths.servers == "/tmp/test_storage_data/servers"
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
