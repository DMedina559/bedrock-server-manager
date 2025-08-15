import pytest
from unittest.mock import patch, MagicMock

from bedrock_server_manager.api.plugins import (
    get_plugin_statuses,
    set_plugin_status,
    reload_plugins,
    trigger_external_plugin_event_api,
)
from bedrock_server_manager.error import UserInputError


@pytest.fixture
def mock_plugin_manager():
    """Fixture for a mocked PluginManager."""
    manager = MagicMock()
    manager.plugin_config = {
        "plugin1": {"enabled": True, "version": "1.0", "description": "A test plugin."}
    }
    return manager


@pytest.fixture
def mock_get_plugin_manager_instance(mock_plugin_manager):
    """Fixture to patch get_plugin_manager_instance."""
    with patch(
        "bedrock_server_manager.api.plugins.get_plugin_manager_instance",
        return_value=mock_plugin_manager,
    ) as mock:
        yield mock


class TestPluginAPI:
    def test_get_plugin_statuses(
        self, mock_get_plugin_manager_instance, mock_plugin_manager
    ):
        result = get_plugin_statuses()
        assert result["status"] == "success"
        assert result["plugins"] == mock_plugin_manager.plugin_config

    def test_set_plugin_status_enable(
        self, mock_get_plugin_manager_instance, mock_plugin_manager
    ):
        result = set_plugin_status("plugin1", True)
        assert result["status"] == "success"
        assert mock_plugin_manager.plugin_config["plugin1"]["enabled"] is True
        mock_plugin_manager._save_config.assert_called_once()

    def test_set_plugin_status_disable(
        self, mock_get_plugin_manager_instance, mock_plugin_manager
    ):
        result = set_plugin_status("plugin1", False)
        assert result["status"] == "success"
        assert mock_plugin_manager.plugin_config["plugin1"]["enabled"] is False
        mock_plugin_manager._save_config.assert_called_once()

    def test_set_plugin_status_not_found(self, mock_get_plugin_manager_instance):
        with pytest.raises(UserInputError):
            set_plugin_status("non_existent_plugin", True)

    def test_set_plugin_status_empty_name(self):
        with pytest.raises(UserInputError):
            set_plugin_status("", True)

    def test_reload_plugins(
        self, mock_get_plugin_manager_instance, mock_plugin_manager
    ):
        result = reload_plugins()
        assert result["status"] == "success"
        mock_plugin_manager.reload.assert_called_once()

    def test_trigger_external_plugin_event_api(
        self, mock_get_plugin_manager_instance, mock_plugin_manager
    ):
        result = trigger_external_plugin_event_api("my_event:test", {"key": "value"})
        assert result["status"] == "success"
        mock_plugin_manager.trigger_custom_plugin_event.assert_called_once_with(
            "my_event:test", "external_api_trigger", key="value"
        )

    def test_trigger_external_plugin_event_api_no_payload(
        self, mock_get_plugin_manager_instance, mock_plugin_manager
    ):
        result = trigger_external_plugin_event_api("my_event:test")
        assert result["status"] == "success"
        mock_plugin_manager.trigger_custom_plugin_event.assert_called_once_with(
            "my_event:test", "external_api_trigger"
        )

    def test_trigger_external_plugin_event_api_empty_event(self):
        with pytest.raises(UserInputError):
            trigger_external_plugin_event_api("")
