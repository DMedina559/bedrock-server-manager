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
    with patch("uvicorn.Server.run") as mock_run:
        result = start_web_server(
            request=StartWebServerRequest(mode="direct"), app_context=app_context
        ).model_dump(mode="python")

        assert result["status"] == "success"
        mock_run.assert_called_once()
        assert app_context._web_server is not None
        assert app_context._web_server.config.app.state.app_context is app_context


def test_start_web_server_invalid_mode(app_context: AppContext):
    """Test starting web server with invalid mode raises UserInputError."""
    # The API catches the error and returns a status dictionary
    with pytest.raises(ValidationError):
        start_web_server(
            request=StartWebServerRequest.model_validate({"mode": "invalid"}),
            app_context=app_context,
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


def test_detached_start_rejects_verified_existing_process(app_context, monkeypatch):
    from unittest.mock import AsyncMock

    from bedrock_server_manager.api import web
    from bedrock_server_manager.error import OperationConflictError

    launch = AsyncMock()
    remove = AsyncMock()
    for name, value in {
        "read_pid_from_file": AsyncMock(return_value=1234),
        "is_process_running": AsyncMock(return_value=True),
        "verify_process_identity": AsyncMock(return_value=None),
        "launch_detached_process": launch,
        "remove_pid_file_if_exists": remove,
    }.items():
        monkeypatch.setattr(web.system_process_utils, name, value)
    with pytest.raises(OperationConflictError):
        start_web_server(
            StartWebServerRequest(mode="detached"), app_context=app_context
        )
    launch.assert_not_awaited()
    remove.assert_not_awaited()


@pytest.mark.parametrize("enabled", [False, True])
def test_service_query_failures_are_unavailable(systemd, enabled):
    from bedrock_server_manager.core import service
    from bedrock_server_manager.error import DependencyUnavailableError

    query = service.is_web_service_enabled if enabled else service.is_web_service_active
    assert query() is False
    systemd.failure = "is-enabled" if enabled else "is-active"
    with pytest.raises(DependencyUnavailableError):
        query()


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("code", [1060, 5])
def test_windows_service_query_only_treats_missing_service_as_negative(
    monkeypatch, enabled, code
):
    import subprocess

    from bedrock_server_manager.core import service
    from bedrock_server_manager.error import DependencyUnavailableError

    monkeypatch.setattr(service.platform, "system", lambda: "Windows")
    monkeypatch.setattr(service.shutil, "which", lambda command: "sc.exe")

    def failed(*args, **kwargs):
        raise subprocess.CalledProcessError(code, "sc.exe")

    monkeypatch.setattr(service.subprocess, "check_output", failed)
    query = service.is_web_service_enabled if enabled else service.is_web_service_active
    if code == 1060:
        assert query() is False
    else:
        with pytest.raises(DependencyUnavailableError):
            query()


@pytest.mark.parametrize(
    "enabled,output,expected",
    [
        (False, "STATE : 4 RUNNING", True),
        (False, "STATE : 1 STOPPED", False),
        (True, "START_TYPE : 2 AUTO_START", True),
        (True, "START_TYPE : 3 DEMAND_START", False),
    ],
)
def test_windows_service_states_are_parsed(monkeypatch, enabled, output, expected):
    from bedrock_server_manager.core import service

    monkeypatch.setattr(service.platform, "system", lambda: "Windows")
    monkeypatch.setattr(service.shutil, "which", lambda command: "sc.exe")
    monkeypatch.setattr(
        service.subprocess, "check_output", lambda *args, **kwargs: output
    )
    query = service.is_web_service_enabled if enabled else service.is_web_service_active
    assert query() is expected


def test_unavailable_service_manager_is_not_reported_as_success(
    app_context, monkeypatch
):
    from bedrock_server_manager.api import web
    from bedrock_server_manager.error import DependencyUnavailableError

    monkeypatch.setattr(web, "can_manage_services", lambda: False)
    with pytest.raises(DependencyUnavailableError):
        get_web_ui_service_status(
            GetWebUiServiceStatusRequest(), app_context=app_context
        )
