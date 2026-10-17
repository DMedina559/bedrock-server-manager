import copy

import pytest
from pydantic import ValidationError

from bedrock_server_manager.state.settings import SettingsState


def test_settings_reject_invalid_update_atomically():
    state = SettingsState()
    original = state.model_dump()
    with pytest.raises(ValidationError):
        state.set("web.port", "invalid")
    assert state.model_dump() == original
    assert not state.is_dirty
    with pytest.raises(ValidationError):
        state.set("web.porrt", 9000)
    assert state.model_dump() == original
    state.set("nullable", None)
    assert "nullable" in state.custom
    state.set("plugin_settings", {"a.b": {"enabled": False}})
    assert state.plugin_settings == {"a.b": {"enabled": False}}
    assert state.get("model_dump") is None


def test_legacy_monitoring_key_is_normalized_on_load():
    settings = SettingsState.from_dict({"monitoring.max_retiries": 7})
    assert settings.monitoring.max_retries == 7
    assert "max_retiries" not in settings.to_dict()["monitoring"]


@pytest.mark.parametrize("layout", ["sections", "dotted", "mixed"])
def test_removed_legacy_settings_are_ignored_on_load(layout, caplog):
    data = {
        "paths": {"servers": "/srv/bedrock", "backups": "/srv/backups"},
        "retention": {"backups": 5, "downloads": 2},
        "web": {"port": 12345, "jwt_secret_key": "keep-secret"},
        "custom": {"example": {"logs": "keep", "threads": 8}},
        "plugin_settings": {"example": {"logs": True, "threads": 2}},
    }
    for section, name, value in (
        ("paths", "logs", "/private/old-logs"),
        ("retention", "logs", 3),
        ("web", "threads", 4),
    ):
        if layout in ("sections", "mixed"):
            data[section][name] = value
        if layout in ("dotted", "mixed"):
            data[f"{section}.{name}"] = value
    original = copy.deepcopy(data)

    settings = SettingsState.from_dict(data)

    assert settings.paths.servers == "/srv/bedrock"
    assert settings.paths.backups == "/srv/backups"
    assert settings.retention.backups == 5
    assert settings.retention.downloads == 2
    assert settings.web.port == 12345
    assert settings.web.jwt_secret_key == "keep-secret"
    assert settings.custom == original["custom"]
    assert settings.plugin_settings == original["plugin_settings"]
    for section, name in (("paths", "logs"), ("retention", "logs"), ("web", "threads")):
        assert name not in settings.to_dict()[section]
        assert f"Ignoring removed legacy setting {section}.{name}" in caplog.text
    assert "/private/old-logs" not in caplog.text
    assert "keep-secret" not in caplog.text
    assert data == original
    assert not settings.is_dirty
    assert SettingsState.from_dict(settings.to_dict()).to_dict() == settings.to_dict()


@pytest.mark.parametrize("key", ["paths.logs", "retention.logs", "web.threads"])
def test_removed_settings_are_still_rejected_on_update(key):
    settings = SettingsState()
    original = settings.to_dict()
    with pytest.raises(ValidationError):
        settings.set(key, 4)
    assert settings.to_dict() == original
    assert not settings.is_dirty


@pytest.mark.parametrize("section", ["paths", "retention", "web"])
def test_unknown_nested_settings_are_still_rejected_on_load(section):
    with pytest.raises(ValidationError):
        SettingsState.from_dict({section: {"unknown_field": 4}})
