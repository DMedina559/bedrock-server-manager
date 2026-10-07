from unittest.mock import patch

import pytest
from pydantic import ValidationError

from bedrock_server_manager.api.models import (
    CreateWebUiServiceRequest,
    DisableWebUiServiceRequest,
    EnableWebUiServiceRequest,
    GetWebServerStatusRequest,
    GetWebUiServiceStatusRequest,
    RemoveWebUiServiceRequest,
    StartWebServerRequest,
    StopWebServerRequest,
)
from bedrock_server_manager.api.web import (
    create_web_ui_service,
    disable_web_ui_service,
    enable_web_ui_service,
    get_web_server_status,
    get_web_ui_service_status,
    remove_web_ui_service,
    start_web_server,
    stop_web_server,
)
from bedrock_server_manager.context import AppContext
from bedrock_server_manager.error import BSMError, SystemError

"""
Integration tests for the API functions in bedrock_server_manager/api/web.py.
"""


def test_start_web_server_direct_success(app_context: AppContext):
    """Test starting web server directly."""
    with patch("bedrock_server_manager.web.main.run_web_server") as mock_run:
        result = start_web_server(
            request=StartWebServerRequest(mode="direct"), app_context=app_context
        ).model_dump(mode="python")

        assert result["status"] == "success"
        mock_run.assert_called_once()


def test_start_web_server_invalid_mode(app_context: AppContext):
    """Test starting web server with invalid mode raises UserInputError."""
    # The API catches the error and returns a status dictionary
    with pytest.raises(ValidationError):
        start_web_server(
            request=StartWebServerRequest(mode="invalid"), app_context=app_context
        ).model_dump(mode="python")


def test_start_web_server_detached_success(app_context: AppContext):
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
                result = start_web_server(
                    request=StartWebServerRequest(mode="detached"),
                    app_context=app_context,
                ).model_dump(mode="python")

                assert result["status"] == "success"
                assert result["pid"] == 1234
                mock_launch.assert_called_once()


def test_stop_web_server_success(app_context: AppContext):
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
                            result = stop_web_server(
                                request=StopWebServerRequest(), app_context=app_context
                            ).model_dump(mode="python")

                            assert result["status"] == "success"
                            mock_terminate.assert_called_once_with(1234)


def test_stop_web_server_no_psutil(app_context: AppContext):
    """Test stopping the detached web server when psutil is not available."""
    with patch("bedrock_server_manager.api.web.PSUTIL_AVAILABLE", False):
        with pytest.raises(SystemError):
            stop_web_server(
                request=StopWebServerRequest(), app_context=app_context
            ).model_dump(mode="python")


def test_get_web_server_status_running(app_context: AppContext):
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
                    result = get_web_server_status(
                        request=GetWebServerStatusRequest(), app_context=app_context
                    ).model_dump(mode="python")

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
                result = create_web_ui_service(
                    request=CreateWebUiServiceRequest(autostart=True),
                    app_context=app_context,
                ).model_dump(mode="python")

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
                result = create_web_ui_service(
                    request=CreateWebUiServiceRequest(autostart=False),
                    app_context=app_context,
                ).model_dump(mode="python")

                assert result["status"] == "success"
                mock_create.assert_called_once()
                mock_disable.assert_called_once()


def test_create_web_ui_service_cannot_manage(app_context: AppContext):
    """Test creating a web ui service when management tools are missing."""
    with patch(
        "bedrock_server_manager.api.web.can_manage_services", return_value=False
    ):
        with pytest.raises(BSMError):
            create_web_ui_service(
                request=CreateWebUiServiceRequest(autostart=True),
                app_context=app_context,
            ).model_dump(mode="python")


def test_enable_web_ui_service_success(app_context: AppContext):
    """Test enabling web ui service successfully."""
    with patch("bedrock_server_manager.api.web.can_manage_services", return_value=True):
        with patch(
            "bedrock_server_manager.core.service.enable_web_service"
        ) as mock_enable:
            result = enable_web_ui_service(
                request=EnableWebUiServiceRequest(), app_context=app_context
            ).model_dump(mode="python")
            assert result["status"] == "success"
            mock_enable.assert_called_once()


def test_disable_web_ui_service_success(app_context: AppContext):
    """Test disabling web ui service successfully."""
    with patch("bedrock_server_manager.api.web.can_manage_services", return_value=True):
        with patch(
            "bedrock_server_manager.core.service.disable_web_service"
        ) as mock_disable:
            result = disable_web_ui_service(
                request=DisableWebUiServiceRequest(), app_context=app_context
            ).model_dump(mode="python")
            assert result["status"] == "success"
            mock_disable.assert_called_once()


def test_remove_web_ui_service_success(app_context: AppContext):
    """Test removing web ui service successfully."""
    with patch("bedrock_server_manager.api.web.can_manage_services", return_value=True):
        with patch(
            "bedrock_server_manager.core.service.remove_web_service_file",
            return_value=True,
        ) as mock_remove:
            result = remove_web_ui_service(
                request=RemoveWebUiServiceRequest(), app_context=app_context
            ).model_dump(mode="python")
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
                    result = get_web_ui_service_status(
                        request=GetWebUiServiceStatusRequest(), app_context=app_context
                    ).model_dump(mode="python")

                    assert result["status"] == "success"
                    assert result["service_exists"] is True
                    assert result["is_active"] is True
                    assert result["is_enabled"] is False
