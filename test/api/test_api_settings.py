import pytest
from unittest.mock import patch, MagicMock

from bedrock_server_manager.api.settings import (
    get_global_setting,
    get_all_global_settings,
    set_global_setting,
    set_custom_global_setting,
    reload_global_settings,
)
from bedrock_server_manager.error import MissingArgumentError


@pytest.fixture
def mock_api_settings_get_settings_instance(mocker):
    """Fixture to patch get_settings_instance in the api.settings module."""
    mock = MagicMock()
    mocker.patch(
        "bedrock_server_manager.api.settings.get_settings_instance", return_value=mock
    )
    return mock


class TestSettingsAPI:
    def test_get_global_setting(self, mock_api_settings_get_settings_instance):
        mock_api_settings_get_settings_instance.get.return_value = "test_value"
        result = get_global_setting("some.key")
        assert result["status"] == "success"
        assert result["value"] == "test_value"

    def test_get_all_global_settings(self, mock_api_settings_get_settings_instance):
        mock_api_settings_get_settings_instance._settings = {"key": "value"}
        result = get_all_global_settings()
        assert result["status"] == "success"
        assert result["data"] == {"key": "value"}

    def test_set_global_setting(self, mock_api_settings_get_settings_instance):
        result = set_global_setting("some.key", "new_value")
        assert result["status"] == "success"
        mock_api_settings_get_settings_instance.set.assert_called_once_with(
            "some.key", "new_value"
        )

    def test_set_custom_global_setting(self, mock_api_settings_get_settings_instance):
        result = set_custom_global_setting("custom_key", "custom_value")
        assert result["status"] == "success"
        mock_api_settings_get_settings_instance.set.assert_called_once_with(
            "custom.custom_key", "custom_value"
        )

    @patch("bedrock_server_manager.api.settings.setup_logging")
    def test_reload_global_settings(
        self, mock_setup_logging, mock_api_settings_get_settings_instance
    ):
        result = reload_global_settings()
        assert result["status"] == "success"
        mock_api_settings_get_settings_instance.reload.assert_called_once()
        mock_setup_logging.assert_called_once()

    def test_get_global_setting_no_key(self):
        with pytest.raises(MissingArgumentError):
            get_global_setting("")

    def test_set_global_setting_no_key(self):
        with pytest.raises(MissingArgumentError):
            set_global_setting("", "value")
