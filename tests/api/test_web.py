"""
Integration tests for the API functions in bedrock_server_manager/api/web.py.
"""

from unittest.mock import patch

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
from bedrock_server_manager.context import AppContext


def test_start_web_server_api_direct_success(app_context: AppContext):
    """Test starting web server directly."""
    with patch("bedrock_server_manager.web.main.run_web_server") as mock_run:
        result = start_web_server_api(app_context, mode="direct")

        assert result["status"] == "success"
        mock_run.assert_called_once()


def test_start_web_server_api_invalid_mode(app_context: AppContext):
    """Test starting web server with invalid mode raises UserInputError."""
    # The API catches the error and returns a status dictionary
    result = start_web_server_api(app_context, mode="invalid")
    assert result["status"] == "error"
    assert "Invalid mode" in result["message"]


def test_start_web_server_api_detached_success(app_context: AppContext):
    """Test starting web server detached."""
    with patch("bedrock_server_manager.api.web.PSUTIL_AVAILABLE", True):
        with patch(
            "bedrock_server_manager.core.system.process.launch_detached_process"
        ) as mock_launch:
            with patch(
                "bedrock_server_manager.core.system.process.is_process_running",
                return_value=False,
            ):
                mock_launch.return_value = 1234
                result = start_web_server_api(app_context, mode="detached")

                assert result["status"] == "success"
                assert result["pid"] == 1234
                mock_launch.assert_called_once()


def test_stop_web_server_api_success(app_context: AppContext):
    """Test stopping the detached web server."""
    with patch("bedrock_server_manager.api.web.PSUTIL_AVAILABLE", True):
        with patch(
            "bedrock_server_manager.core.system.process.read_pid_from_file",
            return_value=1234,
        ):
            with patch(
                "bedrock_server_manager.core.system.process.is_process_running",
                return_value=True,
            ):
                with patch(
                    "bedrock_server_manager.core.system.process.verify_process_identity"
                ):
                    with patch(
                        "bedrock_server_manager.core.system.process.terminate_process_by_pid"
                    ) as mock_terminate:
                        with patch(
                            "bedrock_server_manager.core.system.process.remove_pid_file_if_exists"
                        ):
                            result = stop_web_server_api(app_context)

                            assert result["status"] == "success"
                            mock_terminate.assert_called_once_with(1234)


def test_stop_web_server_api_no_psutil(app_context: AppContext):
    """Test stopping the detached web server when psutil is not available."""
    with patch("bedrock_server_manager.api.web.PSUTIL_AVAILABLE", False):
        result = stop_web_server_api(app_context)
        assert result["status"] == "error"
        assert "psutil" in result["message"]


def test_get_web_server_status_api_running(app_context: AppContext):
    """Test checking status when it's running."""
    with patch("bedrock_server_manager.api.web.PSUTIL_AVAILABLE", True):
        with patch(
            "bedrock_server_manager.core.system.process.read_pid_from_file",
            return_value=1234,
        ):
            with patch(
                "bedrock_server_manager.core.system.process.is_process_running",
                return_value=True,
            ):
                with patch(
                    "bedrock_server_manager.core.system.process.verify_process_identity"
                ):
                    result = get_web_server_status_api(app_context)

                    assert result["status"] == "RUNNING"
                    assert result["pid"] == 1234


def test_create_web_ui_service_success(app_context: AppContext):
    """Test creating a web ui service successfully."""
    with patch("bedrock_server_manager.api.web.can_manage_services", return_value=True):
        with patch(
            "bedrock_server_manager.core.service.create_web_service_file"
        ) as mock_create:
            with patch(
                "bedrock_server_manager.core.service.enable_web_service"
            ) as mock_enable:
                result = create_web_ui_service(app_context, autostart=True)

                assert result["status"] == "success"
                mock_create.assert_called_once()
                mock_enable.assert_called_once()


def test_create_web_ui_service_disabled(app_context: AppContext):
    """Test creating a web ui service with autostart false."""
    with patch("bedrock_server_manager.api.web.can_manage_services", return_value=True):
        with patch(
            "bedrock_server_manager.core.service.create_web_service_file"
        ) as mock_create:
            with patch(
                "bedrock_server_manager.core.service.disable_web_service"
            ) as mock_disable:
                result = create_web_ui_service(app_context, autostart=False)

                assert result["status"] == "success"
                mock_create.assert_called_once()
                mock_disable.assert_called_once()


def test_create_web_ui_service_cannot_manage(app_context: AppContext):
    """Test creating a web ui service when management tools are missing."""
    with patch(
        "bedrock_server_manager.api.web.can_manage_services", return_value=False
    ):
        result = create_web_ui_service(app_context, autostart=True)
        assert result["status"] == "error"
        assert "not found" in result["message"]


def test_enable_web_ui_service_success(app_context: AppContext):
    """Test enabling web ui service successfully."""
    with patch("bedrock_server_manager.api.web.can_manage_services", return_value=True):
        with patch(
            "bedrock_server_manager.core.service.enable_web_service"
        ) as mock_enable:
            result = enable_web_ui_service(app_context)
            assert result["status"] == "success"
            mock_enable.assert_called_once()


def test_disable_web_ui_service_success(app_context: AppContext):
    """Test disabling web ui service successfully."""
    with patch("bedrock_server_manager.api.web.can_manage_services", return_value=True):
        with patch(
            "bedrock_server_manager.core.service.disable_web_service"
        ) as mock_disable:
            result = disable_web_ui_service(app_context)
            assert result["status"] == "success"
            mock_disable.assert_called_once()


def test_remove_web_ui_service_success(app_context: AppContext):
    """Test removing web ui service successfully."""
    with patch("bedrock_server_manager.api.web.can_manage_services", return_value=True):
        with patch(
            "bedrock_server_manager.core.service.remove_web_service_file",
            return_value=True,
        ) as mock_remove:
            result = remove_web_ui_service(app_context)
            assert result["status"] == "success"
            mock_remove.assert_called_once()


def test_get_web_ui_service_status_success(app_context: AppContext):
    """Test getting web ui service status successfully."""
    with patch("bedrock_server_manager.api.web.can_manage_services", return_value=True):
        with patch(
            "bedrock_server_manager.core.service.check_web_service_exists",
            return_value=True,
        ):
            with patch(
                "bedrock_server_manager.core.service.is_web_service_active",
                return_value=True,
            ):
                with patch(
                    "bedrock_server_manager.core.service.is_web_service_enabled",
                    return_value=False,
                ):
                    result = get_web_ui_service_status(app_context)

                    assert result["status"] == "success"
                    assert result["service_exists"] is True
                    assert result["is_active"] is True
                    assert result["is_enabled"] is False
