from unittest.mock import patch

from bedrock_server_manager.api.system import (
    get_bedrock_process_info,
    get_server_running_status,
)
from bedrock_server_manager.error import BSMError


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

    def test_bsm_error_handling(self, app_context):
        server = app_context.get_server("test_server")
        with patch.object(server, "is_running", side_effect=BSMError("Test error")):
            result = get_server_running_status("test_server", app_context=app_context)
            assert result["status"] == "error"
            assert "Test error" in result["message"]

    def test_get_server_running_status_running(self, app_context):
        server = app_context.get_server("test_server")
        with patch.object(server, "is_running", return_value=True):
            result = get_server_running_status("test_server", app_context=app_context)
            assert result["status"] == "success"
            assert result["is_running"] is True

    def test_get_server_running_status_stopped(self, app_context):
        server = app_context.get_server("test_server")
        with patch.object(server, "is_running", return_value=False):
            result = get_server_running_status("test_server", app_context=app_context)
            assert result["status"] == "success"
            assert result["is_running"] is False
