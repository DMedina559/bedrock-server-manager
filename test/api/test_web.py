import pytest
from unittest.mock import patch, MagicMock

from bedrock_server_manager.api.web import (
    start_web_server_api,
    stop_web_server_api,
    get_web_server_status_api,
    create_web_ui_service,
    enable_web_ui_service,
    disable_web_ui_service,
    remove_web_ui_service,
    get_web_ui_service_status,
)
from bedrock_server_manager.error import SystemError, ServerProcessError


@pytest.fixture
def mock_manager():
    """Fixture for a mocked BedrockServerManager."""
    manager = MagicMock()
    manager.get_web_ui_pid_path.return_value = "/tmp/web.pid"
    manager.get_web_ui_executable_path.return_value = "/usr/bin/python"
    manager.get_web_ui_expected_start_arg.return_value = "web"
    manager.can_manage_services = True
    return manager


@pytest.fixture
def mock_get_manager_instance(mock_manager):
    """Fixture to patch get_manager_instance."""
    with patch(
        "bedrock_server_manager.api.web.get_manager_instance", return_value=mock_manager
    ) as mock:
        yield mock


class TestWebServerLifecycle:
    @patch("bedrock_server_manager.api.web.get_manager_instance")
    def test_start_web_server_direct(self, mock_get_manager):
        mock_manager = mock_get_manager()
        start_web_server_api(mode="direct")
        mock_manager.start_web_ui_direct.assert_called_once()

    @patch("bedrock_server_manager.api.web.system_process_utils")
    @patch("bedrock_server_manager.api.web.PSUTIL_AVAILABLE", True)
    def test_start_web_server_detached(
        self, mock_system_process, mock_get_manager_instance
    ):
        mock_system_process.read_pid_from_file.return_value = None
        mock_system_process.launch_detached_process.return_value = 12345
        result = start_web_server_api(mode="detached")
        assert result["status"] == "success"
        assert result["pid"] == 12345

    @patch("bedrock_server_manager.api.web.system_process_utils")
    @patch("bedrock_server_manager.api.web.PSUTIL_AVAILABLE", True)
    def test_stop_web_server_api(self, mock_system_process, mock_get_manager_instance):
        mock_system_process.read_pid_from_file.return_value = 12345
        mock_system_process.is_process_running.return_value = True
        result = stop_web_server_api()
        assert result["status"] == "success"
        mock_system_process.terminate_process_by_pid.assert_called_once_with(12345)

    @patch("bedrock_server_manager.api.web.system_process_utils")
    @patch("bedrock_server_manager.api.web.PSUTIL_AVAILABLE", True)
    def test_get_web_server_status_api_running(
        self, mock_system_process, mock_get_manager_instance
    ):
        mock_system_process.read_pid_from_file.return_value = 12345
        mock_system_process.is_process_running.return_value = True
        result = get_web_server_status_api()
        assert result["status"] == "RUNNING"
        assert result["pid"] == 12345


class TestWebServiceManagement:
    def test_create_web_ui_service_autostart(
        self, mock_get_manager_instance, mock_manager
    ):
        create_web_ui_service(autostart=True)
        mock_manager.create_web_service_file.assert_called_once()
        mock_manager.enable_web_service.assert_called_once()

    def test_enable_web_ui_service(self, mock_get_manager_instance, mock_manager):
        enable_web_ui_service()
        mock_manager.enable_web_service.assert_called_once()

    def test_disable_web_ui_service(self, mock_get_manager_instance, mock_manager):
        disable_web_ui_service()
        mock_manager.disable_web_service.assert_called_once()

    def test_remove_web_ui_service(self, mock_get_manager_instance, mock_manager):
        mock_manager.remove_web_service_file.return_value = True
        result = remove_web_ui_service()
        assert result["status"] == "success"
        mock_manager.remove_web_service_file.assert_called_once()

    def test_get_web_ui_service_status(self, mock_get_manager_instance, mock_manager):
        mock_manager.check_web_service_exists.return_value = True
        mock_manager.is_web_service_active.return_value = True
        mock_manager.is_web_service_enabled.return_value = True
        result = get_web_ui_service_status()
        assert result["status"] == "success"
        assert result["service_exists"] is True
        assert result["is_active"] is True
        assert result["is_enabled"] is True
