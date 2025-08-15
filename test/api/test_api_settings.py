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
def mock_settings():
    """Fixture for a mocked Settings object."""
    settings = MagicMock()
    settings.get.return_value = "test_value"
    settings._settings = {"key": "value"}
    return settings


@pytest.fixture
def mock_get_settings_instance(mock_settings):
    """Fixture to patch get_settings_instance."""
    with patch(
        "bedrock_server_manager.api.settings.get_settings_instance",
        return_value=mock_settings,
    ) as mock:
        yield mock


class TestSettingsAPI:
    def test_get_global_setting(self, mock_get_settings_instance):
        result = get_global_setting("some.key")
        assert result["status"] == "success"
        assert result["value"] == "test_value"

    def test_get_all_global_settings(self, mock_get_settings_instance):
        result = get_all_global_settings()
        assert result["status"] == "success"
        assert result["data"] == {"key": "value"}

    def test_set_global_setting(self, mock_get_settings_instance, mock_settings):
        result = set_global_setting("some.key", "new_value")
        assert result["status"] == "success"
        mock_settings.set.assert_called_once_with("some.key", "new_value")

    def test_set_custom_global_setting(self, mock_get_settings_instance, mock_settings):
        result = set_custom_global_setting("custom_key", "custom_value")
        assert result["status"] == "success"
        mock_settings.set.assert_called_once_with("custom.custom_key", "custom_value")

    @patch("bedrock_server_manager.api.settings.setup_logging")
    def test_reload_global_settings(
        self, mock_setup_logging, mock_get_settings_instance, mock_settings
    ):
        result = reload_global_settings()
        assert result["status"] == "success"
        mock_settings.reload.assert_called_once()
        mock_setup_logging.assert_called_once()

    def test_get_global_setting_no_key(self):
        with pytest.raises(MissingArgumentError):
            get_global_setting("")

    def test_set_global_setting_no_key(self):
        with pytest.raises(MissingArgumentError):
            set_global_setting("", "value")
