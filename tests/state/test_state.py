# tests/test_state.py
"""
Unit tests for AppState and its sub-states.
"""

import os

import pytest

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


def test_app_state_defaults():
    state = AppState()
    assert isinstance(state.settings, SettingsState)
    assert isinstance(state.servers, ServerState)
    assert isinstance(state.plugins, PluginState)
    assert isinstance(state.users, UserState)
    assert isinstance(state.runtime, RuntimeState)
    assert not state.is_dirty()


def test_settings_state_create_defaults():
    test_dir = "/tmp/test_data"
    settings = SettingsState.create_defaults(test_dir)
    assert settings.paths.servers == os.path.join(test_dir, "servers")
    assert settings.paths.backups == os.path.join(test_dir, "backups")
    assert settings.retention.backups == 3
    assert settings.web.port == 11325


def test_settings_state_get_and_set():
    settings = SettingsState.create_defaults("/tmp/test_data")
    assert not settings.is_dirty

    # Test set typed field
    settings.set("paths.servers", "/custom/servers")
    assert settings.get("paths.servers") == "/custom/servers"
    assert settings.is_dirty
    assert "paths" in settings.dirty_keys

    # Test set custom nested field
    settings.set("custom.my_plugin.enabled", True)
    assert settings.get("custom.my_plugin.enabled") is True

    # Test clear dirty
    settings.clear_dirty()
    assert not settings.is_dirty
    assert len(settings.dirty_keys) == 0


def test_settings_state_serialization():
    settings = SettingsState.create_defaults("/tmp/test_data")
    settings.set("paths.servers", "/opt/mc/servers")
    d = settings.to_dict()
    assert d["paths"]["servers"] == "/opt/mc/servers"

    reconstructed = SettingsState.from_dict(d)
    assert reconstructed.paths.servers == "/opt/mc/servers"


def test_app_state_dirty_tracking():
    app_state = AppState()
    assert not app_state.is_dirty()

    app_state.settings.mark_dirty("paths")
    assert app_state.is_dirty()

    app_state.clear_dirty()
    assert not app_state.is_dirty()

    app_state.servers.mark_dirty()
    assert app_state.is_dirty()


def test_server_state():
    server_state = ServerState()
    assert not server_state.is_dirty

    cfg = ServerConfigState(
        server_name="survival",
        installed_version="1.20.50.03",
        status="STOPPED",
        autostart=True,
    )
    server_state.set(cfg)

    assert server_state.is_dirty
    assert "survival" in server_state.dirty_servers
    assert server_state.get("survival") == cfg

    server_state.clear_dirty()
    assert not server_state.is_dirty
    assert len(server_state.dirty_servers) == 0


def test_plugin_and_user_state():
    plugin_state = PluginState()
    p_info = PluginInfoState(
        plugin_name="backup_plugin",
        enabled=True,
        version="1.0.0",
        author="BSM",
        description="Backup plugin",
    )
    plugin_state.set(p_info)
    assert plugin_state.is_dirty
    assert "backup_plugin" in plugin_state.dirty_plugins
    assert plugin_state.get("backup_plugin") == p_info

    user_state = UserState()
    u_info = UserInfoState(
        id=1,
        username="admin",
        role="admin",
        theme="dark",
        is_active=True,
    )
    user_state.set(u_info)
    assert user_state.is_dirty
    assert "admin" in user_state.dirty_users
    assert user_state.get("admin") == u_info


def test_settings_state_security_private_and_dunder_keys():
    settings = SettingsState.create_defaults("/tmp/test_data")

    # Accessing private/dunder attributes should raise ConfigurationError
    with pytest.raises(ConfigurationError):
        settings.get("_locks")

    with pytest.raises(ConfigurationError):
        settings.get("__class__")

    with pytest.raises(ConfigurationError):
        settings.set("_dirty", True)

    with pytest.raises(ConfigurationError):
        settings.set("custom.__class__", "evil")


def test_state_models_deep_copy_isolation():
    server_state = ServerState()
    cfg = ServerConfigState(
        server_name="survival",
        custom={"motd": "Original"},
    )
    server_state.set(cfg)

    # Retrieve snapshot and mutate it externally
    snapshot = server_state.get("survival")
    assert snapshot is not None
    snapshot.custom["motd"] = "Hacked"

    # Verify original state model inside ServerState remains unchanged
    internal_cfg = server_state.get("survival")
    assert internal_cfg is not None
    assert internal_cfg.custom["motd"] == "Original"


def test_revisions_are_unique_across_threads_and_epochs_change_per_instance():
    from concurrent.futures import ThreadPoolExecutor

    from bedrock_server_manager.state.revision import RevisionClock

    clock = RevisionClock()
    with ThreadPoolExecutor(max_workers=8) as executor:
        revisions = list(executor.map(lambda _: clock.capture(), range(200)))
    assert sorted(revision["revision"] for revision in revisions) == list(range(1, 201))
    assert {revision["epoch"] for revision in revisions} == {clock.epoch}
    assert RevisionClock().epoch != clock.epoch


def test_state_revision_requires_complete_valid_metadata():
    from pydantic import ValidationError

    from bedrock_server_manager.api.models.common import StateRevision

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
    from sqlalchemy import select

    from bedrock_server_manager.db.models import Server
    from bedrock_server_manager.state.changeset import ChangeSet

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
