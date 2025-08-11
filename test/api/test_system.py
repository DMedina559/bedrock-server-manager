import pytest
from unittest.mock import patch, MagicMock

from bedrock_server_manager.api.system import (
    get_bedrock_process_info,
    set_autoupdate,
)
from bedrock_server_manager.error import UserInputError


class TestSystemAPI:
    def test_get_bedrock_process_info_running(self, app_context):
        server = app_context.get_server("test_server")
        with patch.object(
            server, "get_process_info", return_value={"pid": 123}
        ) as mock_get_info:
            result = get_bedrock_process_info("test_server", app_context=app_context)
            assert result["status"] == "success"
            assert result["process_info"]["pid"] == 123
            mock_get_info.assert_called_once()

    def test_get_bedrock_process_info_not_running(self, app_context):
        server = app_context.get_server("test_server")
        with patch.object(
            server, "get_process_info", return_value=None
        ) as mock_get_info:
            result = get_bedrock_process_info("test_server", app_context=app_context)
            assert result["status"] == "success"
            assert result["process_info"] is None
            mock_get_info.assert_called_once()

    def test_set_autoupdate_true(self, app_context):
        server = app_context.get_server("test_server")
        with patch.object(server, "set_autoupdate") as mock_set_autoupdate:
            result = set_autoupdate("test_server", "true", app_context=app_context)
            assert result["status"] == "success"
            mock_set_autoupdate.assert_called_once_with(True)

    def test_set_autoupdate_false(self, app_context):
        server = app_context.get_server("test_server")
        with patch.object(server, "set_autoupdate") as mock_set_autoupdate:
            result = set_autoupdate("test_server", "false", app_context=app_context)
            assert result["status"] == "success"
            mock_set_autoupdate.assert_called_once_with(False)

    def test_set_autoupdate_invalid(self, app_context):
        with pytest.raises(UserInputError):
            set_autoupdate("test_server", "invalid", app_context=app_context)
