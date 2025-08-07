import pytest
from unittest.mock import patch, MagicMock

from bedrock_server_manager.api.plugins import (
    get_plugin_statuses,
    set_plugin_status,
    reload_plugins,
    trigger_external_plugin_event_api,
)
from bedrock_server_manager.error import UserInputError


class TestPluginAPI:
    def test_get_plugin_statuses(self, real_plugin_manager):
        result = get_plugin_statuses(real_plugin_manager)
        assert result["status"] == "success"
        assert "plugin1" in result["plugins"]

    def test_set_plugin_status_enable(self, real_plugin_manager):
        result = set_plugin_status(real_plugin_manager, "plugin1", True)
        assert result["status"] == "success"
        assert real_plugin_manager.plugin_config["plugin1"]["enabled"] is True

    def test_set_plugin_status_disable(self, real_plugin_manager):
        result = set_plugin_status(real_plugin_manager, "plugin1", False)
        assert result["status"] == "success"
        assert real_plugin_manager.plugin_config["plugin1"]["enabled"] is False

    def test_set_plugin_status_not_found(self, real_plugin_manager):
        with pytest.raises(UserInputError):
            set_plugin_status(real_plugin_manager, "non_existent_plugin", True)

    def test_set_plugin_status_empty_name(self, real_plugin_manager):
        with pytest.raises(UserInputError):
            set_plugin_status(real_plugin_manager, "", True)

    def test_reload_plugins(self, real_plugin_manager):
        with patch.object(real_plugin_manager, "reload") as mock_reload:
            result = reload_plugins(real_plugin_manager)
            assert result["status"] == "success"
            mock_reload.assert_called_once()

    def test_trigger_external_plugin_event_api(self, real_plugin_manager):
        with patch.object(
            real_plugin_manager, "trigger_custom_plugin_event"
        ) as mock_trigger:
            result = trigger_external_plugin_event_api(
                real_plugin_manager, "my_event:test", {"key": "value"}
            )
            assert result["status"] == "success"
            mock_trigger.assert_called_once_with(
                "my_event:test", "external_api_trigger", key="value"
            )

    def test_trigger_external_plugin_event_api_no_payload(self, real_plugin_manager):
        with patch.object(
            real_plugin_manager, "trigger_custom_plugin_event"
        ) as mock_trigger:
            result = trigger_external_plugin_event_api(
                real_plugin_manager, "my_event:test"
            )
            assert result["status"] == "success"
            mock_trigger.assert_called_once_with(
                "my_event:test", "external_api_trigger"
            )

    def test_trigger_external_plugin_event_api_empty_event(self, real_plugin_manager):
        with pytest.raises(UserInputError):
            trigger_external_plugin_event_api(real_plugin_manager, "")
