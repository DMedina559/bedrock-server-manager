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
