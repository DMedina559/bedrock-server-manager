# tests/test_state.py
"""
Unit tests for AppState and its sub-states.
"""

from bedrock_server_manager.state import (
    AppState,
    PluginState,
    RuntimeState,
    ServerState,
    SettingsState,
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
    settings = SettingsState.create_defaults("/tmp/test_data")
    assert settings.paths.servers == "/tmp/test_data/servers"
    assert settings.paths.backups == "/tmp/test_data/backups"
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
