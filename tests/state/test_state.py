"""Unit tests for AppState and its sub-states."""

import os
from concurrent.futures import ThreadPoolExecutor

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from bedrock_server_manager.api.models.common import StateRevision
from bedrock_server_manager.db.models import Server
from bedrock_server_manager.error import ConfigurationError
from bedrock_server_manager.state import (
    AppState,
    PluginInfoState,
    PluginState,
    RuntimeState,
    ServerConfigState,
    ServerState,
    SettingsState,
    UserInfoState,
    UserState,
)
from bedrock_server_manager.state.changeset import ChangeSet
from bedrock_server_manager.state.revision import RevisionClock


def test_app_state_and_substates_in_memory():
    state = AppState()
    assert isinstance(state.settings, SettingsState)
    assert isinstance(state.servers, ServerState)
    assert isinstance(state.plugins, PluginState)
    assert isinstance(state.users, UserState)
    assert isinstance(state.runtime, RuntimeState)
    assert not state.is_dirty()

    state.settings.mark_dirty("paths")
    assert state.is_dirty()
    state.clear_dirty()
    assert not state.is_dirty()
    state.servers.mark_dirty()
    assert state.is_dirty()

    # SettingsState defaults, get, set, serialization, security
    test_dir = "/tmp/test_data"
    settings = SettingsState.create_defaults(test_dir)
    assert settings.paths.servers == os.path.join(test_dir, "servers")
    assert settings.paths.backups == os.path.join(test_dir, "backups")
    assert settings.retention.backups == 3
    assert settings.web.port == 11325
    assert not settings.is_dirty

    settings.set("paths.servers", "/custom/servers")
    assert settings.get("paths.servers") == "/custom/servers"
    assert settings.is_dirty and "paths" in settings.dirty_keys

    settings.set("custom.my_plugin.enabled", True)
    assert settings.get("custom.my_plugin.enabled") is True
    settings.clear_dirty()
    assert not settings.is_dirty and len(settings.dirty_keys) == 0

    d = settings.to_dict()
    assert d["paths"]["servers"] == "/custom/servers"
    reconstructed = SettingsState.from_dict(d)
    assert reconstructed.paths.servers == "/custom/servers"

    for bad_get in ("_locks", "__class__"):
        with pytest.raises(ConfigurationError):
            settings.get(bad_get)
    for bad_set, val in (("_dirty", True), ("custom.__class__", "evil")):
        with pytest.raises(ConfigurationError):
            settings.set(bad_set, val)

    # ServerState and deep-copy isolation
    server_state = ServerState()
    assert not server_state.is_dirty
    cfg = ServerConfigState(
        server_name="survival",
        installed_version="1.20.50.03",
        status="STOPPED",
        autostart=True,
        custom={"motd": "Original"},
    )
    server_state.set(cfg)
    assert server_state.is_dirty and "survival" in server_state.dirty_servers
    assert server_state.get("survival") == cfg
    server_state.clear_dirty()
    assert not server_state.is_dirty and len(server_state.dirty_servers) == 0

    snapshot = server_state.get("survival")
    snapshot.custom["motd"] = "Hacked"
    assert server_state.get("survival").custom["motd"] == "Original"

    # PluginState and UserState
    plugin_state = PluginState()
    p_info = PluginInfoState(
        plugin_name="backup_plugin",
        enabled=True,
        version="1.0.0",
        author="BSM",
        description="Backup plugin",
    )
    plugin_state.set(p_info)
    assert plugin_state.is_dirty and "backup_plugin" in plugin_state.dirty_plugins
    assert plugin_state.get("backup_plugin") == p_info

    user_state = UserState()
    u_info = UserInfoState(
        id=1, username="admin", role="admin", theme="dark", is_active=True
    )
    user_state.set(u_info)
    assert user_state.is_dirty and "admin" in user_state.dirty_users
    assert user_state.get("admin") == u_info


def test_revisions_and_metadata_validation():
    clock = RevisionClock()
    with ThreadPoolExecutor(max_workers=8) as executor:
        revisions = list(executor.map(lambda _: clock.capture(), range(200)))
    assert sorted(revision["revision"] for revision in revisions) == list(range(1, 201))
    assert {revision["epoch"] for revision in revisions} == {clock.epoch}
    assert RevisionClock().epoch != clock.epoch

    assert StateRevision().epoch is None
    assert StateRevision(epoch="instance", revision=1).revision == 1
    for data in (
        {"epoch": "instance"},
        {"revision": 1},
        {"epoch": " ", "revision": 1},
        {"epoch": "instance", "revision": 2**53},
    ):
        with pytest.raises(ValidationError):
            StateRevision(**data)


async def test_changeset_apply_to_storage(db, storage):
    state = AppState()
    await storage.load_state(state)

    cfg = ServerConfigState(
        server_name="changeset_server",
        installed_version="1.20",
        status="STOPPED",
        autostart=True,
    )
    state.servers.set(cfg)

    cs = ChangeSet()
    cs.add_server("changeset_server")
    assert not cs.is_empty()

    await storage.apply_changeset(state, cs)

    async with db.session_manager() as session:
        res = await session.execute(
            select(Server).filter_by(server_name="changeset_server")
        )
        rec = res.scalars().first()
        assert rec is not None
        assert rec.autostart is True
