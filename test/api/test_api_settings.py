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
def mock_get_settings_instance(mocker):
    """Fixture to patch get_settings_instance in the api.settings module."""
    mock = MagicMock()
    mocker.patch(
        "bedrock_server_manager.api.settings.get_settings_instance", return_value=mock
    )
    return mock


class TestSettingsAPI:
    def test_get_global_setting(self, isolated_settings):
        # The isolated_settings fixture creates a default config
        result = get_global_setting("paths.servers")
        assert result["status"] == "success"
        assert "servers" in result["value"]

    def test_get_all_global_settings(self, isolated_settings):
        result = get_all_global_settings()
        assert result["status"] == "success"
        assert "paths" in result["data"]
        assert "servers" in result["data"]["paths"]

    def test_set_global_setting(self, isolated_settings):
        from bedrock_server_manager.db.models import Setting
        from bedrock_server_manager.db.database import db_session_manager

        result = set_global_setting("retention.backups", 5)
        assert result["status"] == "success"

        with db_session_manager() as db_session:
            setting = db_session.query(Setting).filter_by(key="retention").one()
            assert setting.value["backups"] == 5

    def test_set_custom_global_setting(self, isolated_settings):
        from bedrock_server_manager.db.models import Setting
        from bedrock_server_manager.db.database import db_session_manager

        result = set_custom_global_setting("custom_key", "custom_value")
        assert result["status"] == "success"

        with db_session_manager() as db_session:
            setting = db_session.query(Setting).filter_by(key="custom").one()
            assert setting.value["custom_key"] == "custom_value"

    @patch("bedrock_server_manager.api.settings.setup_logging")
    def test_reload_global_settings(self, mock_setup_logging, isolated_settings):
        with patch(
            "bedrock_server_manager.config.settings.Settings.reload"
        ) as mock_reload:
            result = reload_global_settings()
            assert result["status"] == "success"
            mock_reload.assert_called_once()
            mock_setup_logging.assert_called_once()

    def test_get_global_setting_no_key(self):
        with pytest.raises(MissingArgumentError):
            get_global_setting("")

    def test_set_global_setting_no_key(self):
        with pytest.raises(MissingArgumentError):
            set_global_setting("", "value")
