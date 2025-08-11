import pytest
from unittest.mock import patch, MagicMock

from bedrock_server_manager.api.info import (
    get_server_running_status,
    get_server_config_status,
    get_server_installed_version,
)
from bedrock_server_manager.error import BSMError


class TestServerInfo:
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

    def test_get_server_config_status(self, app_context):
        server = app_context.get_server("test_server")
        # Set a status in the config
        server.set_status_in_config("RUNNING")
        result = get_server_config_status("test_server", app_context=app_context)
        assert result["status"] == "success"
        assert result["config_status"] == "RUNNING"

    def test_get_server_installed_version(self, app_context):
        server = app_context.get_server("test_server")
        # Set a version in the config
        server.set_version("1.2.3")
        result = get_server_installed_version("test_server", app_context=app_context)
        assert result["status"] == "success"
        assert result["installed_version"] == "1.2.3"

    def test_bsm_error_handling(self, app_context):
        server = app_context.get_server("test_server")
        with patch.object(server, "is_running", side_effect=BSMError("Test error")):
            result = get_server_running_status("test_server", app_context=app_context)
            assert result["status"] == "error"
            assert "Test error" in result["message"]
