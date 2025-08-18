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


class TestSettingsAPI:
    def test_get_global_setting(self, app_context):
        # The app_context fixture uses isolated_settings, which creates a default config
        result = get_global_setting("paths.servers", app_context=app_context)
        assert result["status"] == "success"
        assert "servers" in result["value"]

    def test_get_all_global_settings(self, app_context):
        result = get_all_global_settings(app_context=app_context)
        assert result["status"] == "success"
        assert "paths" in result["data"]
        assert "servers" in result["data"]["paths"]

    def test_set_global_setting(self, app_context, db_session):
        from bedrock_server_manager.db.models import Setting

        result = set_global_setting("retention.backups", 5, app_context=app_context)
        assert result["status"] == "success"

        setting = db_session.query(Setting).filter_by(key="retention").one()
        assert setting.value["backups"] == 5

    def test_set_custom_global_setting(self, app_context, db_session):
        from bedrock_server_manager.db.models import Setting

        result = set_custom_global_setting(
            "custom_key", "custom_value", app_context=app_context
        )
        assert result["status"] == "success"

        setting = db_session.query(Setting).filter_by(key="custom").one()
        assert setting.value["custom_key"] == "custom_value"

    @patch("bedrock_server_manager.api.settings.setup_logging")
    def test_reload_global_settings(self, mock_setup_logging, app_context):
        result = reload_global_settings(app_context=app_context)
        assert result["status"] == "success"
        mock_setup_logging.assert_called_once()

    def test_get_global_setting_no_key(self, app_context):
        with pytest.raises(MissingArgumentError):
            get_global_setting("", app_context=app_context)

    def test_set_global_setting_no_key(self, app_context):
        with pytest.raises(MissingArgumentError):
            set_global_setting("", "value", app_context=app_context)
