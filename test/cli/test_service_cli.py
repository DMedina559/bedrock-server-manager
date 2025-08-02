import unittest
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from bedrock_server_manager.cli.service import (
    configure_web_service,
    disable_web_service_cli,
    enable_web_service_cli,
    remove_web_service_cli,
    status_web_service_cli,
    service,
)


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def mock_bsm():
    bsm = MagicMock()
    bsm.can_manage_services = True
    bsm.get_os_type.return_value = "Linux"
    return bsm


@pytest.fixture
def mock_ctx(mock_bsm):
    ctx = MagicMock()
    ctx.obj = {"bsm": mock_bsm}
    return ctx


@pytest.mark.skip(reason="Failing in github actions but passes in other envs")
@patch("bedrock_server_manager.cli.service.interactive_web_service_workflow")
def test_configure_web_service_interactive(mock_interactive_workflow, runner, mock_bsm):
    result = runner.invoke(configure_web_service, obj={"bsm": mock_bsm})

    assert result.exit_code == 0
    mock_interactive_workflow.assert_called_once_with(mock_bsm)


@patch("bedrock_server_manager.cli.service._perform_web_service_configuration")
def test_configure_web_service_non_interactive(mock_perform_config, runner, mock_bsm):
    result = runner.invoke(
        configure_web_service,
        ["--setup-service", "--enable-autostart"],
        obj={"bsm": mock_bsm},
    )

    assert result.exit_code == 0
    mock_perform_config.assert_called_once_with(
        bsm=mock_bsm,
        setup_service=True,
        enable_autostart=True,
    )


@patch("bedrock_server_manager.api.web.enable_web_ui_service")
def test_enable_web_service(mock_enable_api, runner, mock_bsm, mock_ctx):
    mock_enable_api.return_value = {"status": "success"}
    cli = service
    result = runner.invoke(enable_web_service_cli, obj={"bsm": mock_bsm})
    assert result.exit_code == 0
    assert "Web UI service enabled successfully" in result.output
    mock_enable_api.assert_called_once()


@patch("bedrock_server_manager.api.web.disable_web_ui_service")
def test_disable_web_service(mock_disable_api, runner, mock_bsm, mock_ctx):
    mock_disable_api.return_value = {"status": "success"}
    result = runner.invoke(disable_web_service_cli, obj={"bsm": mock_bsm})
    assert result.exit_code == 0
    assert "Web UI service disabled successfully" in result.output
    mock_disable_api.assert_called_once()


@patch("questionary.confirm")
@patch("bedrock_server_manager.api.web.remove_web_ui_service")
def test_remove_web_service(mock_remove_api, mock_confirm, runner, mock_bsm):
    mock_confirm.return_value.ask.return_value = True
    mock_remove_api.return_value = {"status": "success"}
    result = runner.invoke(remove_web_service_cli, obj={"bsm": mock_bsm})

    assert result.exit_code == 0
    assert "Web UI service removed successfully" in result.output
    mock_remove_api.assert_called_once()


@patch("bedrock_server_manager.api.web.get_web_ui_service_status")
def test_status_web_service(mock_status_api, runner, mock_bsm):
    mock_status_api.return_value = {
        "status": "success",
        "service_exists": True,
        "is_active": True,
        "is_enabled": True,
    }
    result = runner.invoke(status_web_service_cli, obj={"bsm": mock_bsm})

    assert result.exit_code == 0
    assert "Service Defined: True" in result.output
    assert "Currently Active (Running): True" in result.output
    assert "Enabled for Autostart: True" in result.output
    mock_status_api.assert_called_once()
