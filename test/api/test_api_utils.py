import pytest
from unittest.mock import patch, MagicMock

from bedrock_server_manager.api.utils import (
    validate_server_exist,
    validate_server_name_format,
    update_server_statuses,
    get_system_and_app_info,
    server_lifecycle_manager,
)
from bedrock_server_manager.error import BSMError, ServerStartError
import os


class TestServerValidation:
    def test_validate_server_exist_success(self, app_context):
        result = validate_server_exist("test_server", app_context=app_context)
        assert result["status"] == "success"

    def test_validate_server_exist_not_installed(self, app_context):
        server = app_context.get_server("test_server")
        # To simulate not installed, we can remove the executable
        os.remove(server.bedrock_executable_path)
        result = validate_server_exist("test_server", app_context=app_context)
        assert result["status"] == "error"
        assert "not installed" in result["message"]

    def test_validate_server_name_format_success(self):
        result = validate_server_name_format("valid-name")
        assert result["status"] == "success"

    def test_validate_server_name_format_invalid(self):
        result = validate_server_name_format("invalid name!")
        assert result["status"] == "error"


class TestStatusAndUpdate:
    def test_update_server_statuses(self, app_context):
        with patch.object(
            app_context.manager,
            "get_servers_data",
            return_value=([{"name": "server1"}, {"name": "server2"}], []),
        ):
            result = update_server_statuses(app_context=app_context)
            assert result["status"] == "success"
            assert "2 servers" in result["message"]

    def test_get_system_and_app_info(self, app_context):
        with (
            patch.object(app_context.manager, "get_os_type", return_value="Linux"),
            patch.object(app_context.manager, "get_app_version", return_value="1.0.0"),
        ):
            result = get_system_and_app_info(app_context=app_context)
            assert result["status"] == "success"
            assert result["data"]["os_type"] == "Linux"
            assert result["data"]["app_version"] == "1.0.0"


class TestServerLifecycleManager:
    @patch("bedrock_server_manager.api.utils.api_stop_server")
    @patch("bedrock_server_manager.api.utils.api_start_server")
    def test_lifecycle_manager_stop_and_restart(
        self, mock_start, mock_stop, app_context
    ):
        server = app_context.get_server("test_server")
        with patch.object(server, "is_running", return_value=True):
            mock_stop.return_value = {"status": "success"}
            mock_start.return_value = {"status": "success"}

            with server_lifecycle_manager(
                "test_server", stop_before=True, app_context=app_context
            ):
                pass

            mock_stop.assert_called_once()
            assert mock_stop.call_args[0][0] == "test_server"
            mock_start.assert_called_once()
            assert mock_start.call_args[0][0] == "test_server"

    @patch("bedrock_server_manager.api.utils.api_stop_server")
    @patch("bedrock_server_manager.api.utils.api_start_server")
    def test_lifecycle_manager_exception(self, mock_start, mock_stop, app_context):
        server = app_context.get_server("test_server")
        with patch.object(server, "is_running", return_value=True):
            mock_stop.return_value = {"status": "success"}
            mock_start.return_value = {"status": "success"}

            with pytest.raises(ValueError):
                with server_lifecycle_manager(
                    "test_server", stop_before=True, app_context=app_context
                ):
                    raise ValueError("Test exception")

            mock_stop.assert_called_once()
            assert mock_stop.call_args[0][0] == "test_server"
            mock_start.assert_called_once()
            assert mock_start.call_args[0][0] == "test_server"

    @patch("bedrock_server_manager.api.utils.api_stop_server")
    @patch("bedrock_server_manager.api.utils.api_start_server")
    def test_lifecycle_manager_restart_on_success_only(
        self, mock_start, mock_stop, app_context
    ):
        server = app_context.get_server("test_server")
        with patch.object(server, "is_running", return_value=True):
            mock_stop.return_value = {"status": "success"}

            with pytest.raises(ValueError):
                with server_lifecycle_manager(
                    "test_server",
                    stop_before=True,
                    restart_on_success_only=True,
                    app_context=app_context,
                ):
                    raise ValueError("Test exception")

            mock_stop.assert_called_once()
            assert mock_stop.call_args[0][0] == "test_server"
            mock_start.assert_not_called()
