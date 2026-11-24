import subprocess
from unittest.mock import patch

import pytest

from bedrock_server_manager.api import web
from bedrock_server_manager.api.models import (
    CreateWebUiServiceRequest,
    DisableWebUiServiceRequest,
    EnableWebUiServiceRequest,
    GetWebUiServiceStatusRequest,
    RemoveWebUiServiceRequest,
)
from bedrock_server_manager.api.web import (
    create_web_ui_service,
    disable_web_ui_service,
    enable_web_ui_service,
    get_web_ui_service_status,
    remove_web_ui_service,
)
from bedrock_server_manager.context import AppContext
from bedrock_server_manager.core import service
from bedrock_server_manager.error import BSMError, DependencyUnavailableError


def test_web_ui_service_api_operations(app_context: AppContext, monkeypatch):
    """Test create, enable, disable, remove, status, and unavailable manager handling."""
    with patch("bedrock_server_manager.api.web.can_manage_services", return_value=True):
        with (
            patch(
                "bedrock_server_manager.core.service.create_web_service_file"
            ) as mock_create,
            patch(
                "bedrock_server_manager.core.service.enable_web_service"
            ) as mock_enable,
            patch(
                "bedrock_server_manager.core.service.disable_web_service"
            ) as mock_disable,
            patch(
                "bedrock_server_manager.core.service.remove_web_service_file",
                return_value=True,
            ) as mock_remove,
            patch(
                "bedrock_server_manager.core.service.check_web_service_exists",
                return_value=True,
            ),
            patch(
                "bedrock_server_manager.core.service.is_web_service_active",
                return_value=True,
            ),
            patch(
                "bedrock_server_manager.core.service.is_web_service_enabled",
                return_value=False,
            ),
        ):
            res1 = create_web_ui_service(
                request=CreateWebUiServiceRequest(autostart=True),
                app_context=app_context,
            ).model_dump(mode="python")
            assert res1["status"] == "success"
            mock_create.assert_called_once()
            mock_enable.assert_called_once()

            res2 = create_web_ui_service(
                request=CreateWebUiServiceRequest(autostart=False),
                app_context=app_context,
            ).model_dump(mode="python")
            assert res2["status"] == "success"
            mock_disable.assert_called_once()

            assert (
                enable_web_ui_service(
                    request=EnableWebUiServiceRequest(), app_context=app_context
                ).status
                == "success"
            )
            assert (
                disable_web_ui_service(
                    request=DisableWebUiServiceRequest(), app_context=app_context
                ).status
                == "success"
            )
            assert (
                remove_web_ui_service(
                    request=RemoveWebUiServiceRequest(), app_context=app_context
                ).status
                == "success"
            )
            mock_remove.assert_called_once()

            status_res = get_web_ui_service_status(
                request=GetWebUiServiceStatusRequest(), app_context=app_context
            ).model_dump(mode="python")
            assert status_res["status"] == "success"
            assert status_res["service_exists"] is True
            assert status_res["is_active"] is True
            assert status_res["is_enabled"] is False

    monkeypatch.setattr(web, "can_manage_services", lambda: False)
    with pytest.raises(BSMError):
        create_web_ui_service(
            request=CreateWebUiServiceRequest(autostart=True),
            app_context=app_context,
        )
    with pytest.raises(DependencyUnavailableError):
        get_web_ui_service_status(
            GetWebUiServiceStatusRequest(), app_context=app_context
        )


def test_systemd_and_windows_service_queries(systemd, monkeypatch):
    for enabled in (False, True):
        systemd.failure = None
        query = (
            service.is_web_service_enabled if enabled else service.is_web_service_active
        )
        assert query() is False
        systemd.failure = "is-enabled" if enabled else "is-active"
        with pytest.raises(DependencyUnavailableError):
            query()

    monkeypatch.setattr(service.platform, "system", lambda: "Windows")
    monkeypatch.setattr(service.shutil, "which", lambda command: "sc.exe")

    for enabled in (False, True):
        query = (
            service.is_web_service_enabled if enabled else service.is_web_service_active
        )
        for code in (1060, 5):
            monkeypatch.setattr(
                service.subprocess,
                "check_output",
                lambda *args, c=code, **kwargs: (_ for _ in ()).throw(
                    subprocess.CalledProcessError(c, "sc.exe")
                ),
            )
            if code == 1060:
                assert query() is False
            else:
                with pytest.raises(DependencyUnavailableError):
                    query()

    for enabled, output, expected in [
        (False, "STATE : 4 RUNNING", True),
        (False, "STATE : 1 STOPPED", False),
        (True, "START_TYPE : 2 AUTO_START", True),
        (True, "START_TYPE : 3 DEMAND_START", False),
    ]:
        monkeypatch.setattr(
            service.subprocess, "check_output", lambda *args, out=output, **kwargs: out
        )
        query = (
            service.is_web_service_enabled if enabled else service.is_web_service_active
        )
        assert query() is expected
