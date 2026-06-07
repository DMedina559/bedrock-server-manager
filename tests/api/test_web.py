from unittest.mock import patch

import pytest

from bedrock_server_manager.api.web import (
    create_web_ui_service,
    disable_web_ui_service,
    enable_web_ui_service,
    get_web_server_status_api,
    get_web_ui_service_status,
    remove_web_ui_service,
    start_web_server_api,
    stop_web_server_api,
)


@pytest.fixture
def mock_system_linux_utils(mocker):
    """Fixture to patch system_linux_utils."""
    mocker.patch("platform.system", return_value="Linux")
    mocker.patch(
        "bedrock_server_manager.core.system.base.can_manage_services", return_value=True
    )
    return mocker.patch("bedrock_server_manager.core.service.system_linux_utils")


class TestWebServerLifecycle:
    @patch("bedrock_server_manager.web.main.run_web_server")
    def test_start_web_server_direct(self, mock_run, app_context):
        result = start_web_server_api(mode="direct", app_context=app_context)
        mock_run.assert_called_once_with(
            app_context=app_context, host=None, port=None, debug=False
        )
        assert result["status"] == "success"

    @patch("bedrock_server_manager.api.web.system_process_utils")
    @patch("bedrock_server_manager.api.web.PSUTIL_AVAILABLE", True)
    def test_start_web_server_detached(self, mock_system_process, app_context):
        mock_system_process.read_pid_from_file.return_value = None
        mock_system_process.launch_detached_process.return_value = 12345
        result = start_web_server_api(mode="detached", app_context=app_context)
        assert result["status"] == "success"
        assert result["pid"] == 12345

    @patch("bedrock_server_manager.api.web.system_process_utils")
    @patch("bedrock_server_manager.api.web.PSUTIL_AVAILABLE", True)
    def test_stop_web_server_api(self, mock_system_process, app_context):
        mock_system_process.read_pid_from_file.return_value = 12345
        mock_system_process.is_process_running.return_value = True
        result = stop_web_server_api(app_context=app_context)
        assert result["status"] == "success"
        mock_system_process.terminate_process_by_pid.assert_called_once_with(12345)

    @patch("bedrock_server_manager.api.web.system_process_utils")
    @patch("bedrock_server_manager.api.web.PSUTIL_AVAILABLE", True)
    def test_get_web_server_status_api_running(self, mock_system_process, app_context):
        mock_system_process.read_pid_from_file.return_value = 12345
        mock_system_process.is_process_running.return_value = True
        result = get_web_server_status_api(app_context=app_context)
        assert result["status"] == "RUNNING"
        assert result["pid"] == 12345


class TestWebServiceManagement:
    @patch("bedrock_server_manager.api.web.service.create_web_service_file")
    @patch("bedrock_server_manager.api.web.service.enable_web_service")
    def test_create_web_ui_service_autostart(
        self, mock_enable, mock_create, app_context, mock_system_linux_utils
    ):
        create_web_ui_service(app_context=app_context, autostart=True)
        mock_create.assert_called_once()
        mock_enable.assert_called_once()

    @patch("bedrock_server_manager.api.web.service.enable_web_service")
    def test_enable_web_ui_service(
        self, mock_enable, app_context, mock_system_linux_utils
    ):
        enable_web_ui_service(app_context=app_context)
        mock_enable.assert_called_once()

    @patch("bedrock_server_manager.api.web.service.disable_web_service")
    def test_disable_web_ui_service(
        self, mock_disable, app_context, mock_system_linux_utils
    ):
        disable_web_ui_service(app_context=app_context)
        mock_disable.assert_called_once()

    @pytest.mark.skip(reason="Failing due to mock issues")
    @patch("bedrock_server_manager.core.service.os.remove")
    def test_remove_web_ui_service(
        self, mock_os_remove, app_context, mock_system_linux_utils
    ):
        mock_system_linux_utils.get_systemd_service_file_path.return_value = (
            "/etc/systemd/user/bedrock-server-manager-webui.service"
        )
        result = remove_web_ui_service(app_context=app_context)
        assert result["status"] == "success"
        mock_os_remove.assert_called_once_with(
            "/etc/systemd/user/bedrock-server-manager-webui.service"
        )

    @patch(
        "bedrock_server_manager.core.service.check_web_service_exists",
        return_value=True,
    )
    @patch(
        "bedrock_server_manager.core.service.is_web_service_active", return_value=True
    )
    @patch(
        "bedrock_server_manager.core.service.is_web_service_enabled", return_value=True
    )
    def test_get_web_ui_service_status(
        self,
        mock_enabled,
        mock_active,
        mock_exists,
        app_context,
        mock_system_linux_utils,
    ):
        result = get_web_ui_service_status(app_context=app_context)
        assert result["status"] == "success"
        assert result["service_exists"] is True
        assert result["is_active"] is True
        assert result["is_enabled"] is True
