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
    def test_get_plugin_statuses(self, app_context):
        result = get_plugin_statuses(app_context)
        assert result["status"] == "success"
        assert "plugin1" in result["plugins"]

    def test_set_plugin_status_enable(self, app_context):
        result = set_plugin_status("plugin1", True, app_context=app_context)
        assert result["status"] == "success"
        assert app_context.plugin_manager.plugin_config["plugin1"]["enabled"] is True

    def test_set_plugin_status_disable(self, app_context):
        result = set_plugin_status("plugin1", False, app_context=app_context)
        assert result["status"] == "success"
        assert app_context.plugin_manager.plugin_config["plugin1"]["enabled"] is False

    def test_set_plugin_status_not_found(self, app_context):
        with pytest.raises(UserInputError):
            set_plugin_status("non_existent_plugin", True, app_context=app_context)

    def test_set_plugin_status_empty_name(self, app_context):
        with pytest.raises(UserInputError):
            set_plugin_status("", True, app_context=app_context)

    def test_reload_plugins(self, app_context):
        with patch.object(app_context.plugin_manager, "reload") as mock_reload:
            result = reload_plugins(app_context)
            assert result["status"] == "success"
            mock_reload.assert_called_once()

    def test_trigger_external_plugin_event_api(self, app_context):
        with patch.object(
            app_context.plugin_manager, "trigger_custom_plugin_event"
        ) as mock_trigger:
            result = trigger_external_plugin_event_api(
                event_name="my_event:test",
                payload={"key": "value"},
                app_context=app_context,
            )
            assert result["status"] == "success"
            mock_trigger.assert_called_once_with(
                "my_event:test", "external_api_trigger", key="value"
            )

    def test_trigger_external_plugin_event_api_no_payload(self, app_context):
        with patch.object(
            app_context.plugin_manager, "trigger_custom_plugin_event"
        ) as mock_trigger:
            result = trigger_external_plugin_event_api(
                event_name="my_event:test", app_context=app_context
            )
            assert result["status"] == "success"
            mock_trigger.assert_called_once_with(
                "my_event:test", "external_api_trigger"
            )

    def test_trigger_external_plugin_event_api_empty_event(self, app_context):
        with pytest.raises(UserInputError):
            trigger_external_plugin_event_api("", app_context=app_context)
