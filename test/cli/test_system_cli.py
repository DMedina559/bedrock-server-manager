import unittest
from unittest.mock import MagicMock, patch

import click
import pytest
from click.testing import CliRunner

from bedrock_server_manager.cli.system import (
    configure_service,
    disable_service,
    enable_service,
    monitor_usage,
    requires_service_manager,
    system,
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


class TestRequiresServiceManager(unittest.TestCase):
    def test_with_service_manager(self):
        @requires_service_manager
        def dummy_command(ctx):
            return "executed"

        mock_bsm = MagicMock()
        mock_bsm.can_manage_services = True

        with patch("click.pass_context") as mock_pass_context:
            decorated_command = dummy_command
            # Simulate the decorator being called
            wrapper = decorated_command.__wrapped__
            # Create a mock context
            mock_ctx_instance = MagicMock()
            mock_ctx_instance.obj = {"bsm": mock_bsm}
            # Call the wrapper with the context
            result = wrapper(mock_ctx_instance)
            self.assertEqual(result, "executed")

    def test_without_service_manager(self):
        @requires_service_manager
        def dummy_command(ctx):
            return "executed"

        mock_bsm = MagicMock()
        mock_bsm.can_manage_services = False
        mock_bsm.get_os_type.return_value = "Linux"

        runner = CliRunner()
        mock_bsm.can_manage_services = False

        @system.command()
        @requires_service_manager
        def test_cmd():
            click.echo("should not be called")

        result = runner.invoke(test_cmd, obj={"bsm": mock_bsm})
        assert result.exit_code == 1
        assert "Error: This command requires a service manager" in result.output


@patch("bedrock_server_manager.cli.system.interactive_service_workflow")
def test_configure_service_interactive(mock_interactive_workflow, runner, mock_bsm):
    result = runner.invoke(
        configure_service, ["--server", "test-server"], obj={"bsm": mock_bsm}
    )

    assert result.exit_code == 0
    mock_interactive_workflow.assert_called_once_with(mock_bsm, "test-server")


@patch("bedrock_server_manager.cli.system._perform_service_configuration")
def test_configure_service_non_interactive(mock_perform_config, runner, mock_bsm):
    result = runner.invoke(
        configure_service,
        [
            "--server",
            "test-server",
            "--autoupdate",
            "--setup-service",
            "--enable-autostart",
        ],
        obj={"bsm": mock_bsm},
    )

    assert result.exit_code == 0
    mock_perform_config.assert_called_once_with(
        bsm=mock_bsm,
        server_name="test-server",
        autoupdate=True,
        setup_service=True,
        enable_autostart=True,
    )


def test_configure_service_no_service_manager_fail(runner, mock_bsm):
    mock_bsm.can_manage_services = False
    result = runner.invoke(
        configure_service,
        ["--server", "test-server", "--setup-service"],
        obj={"bsm": mock_bsm},
    )

    assert result.exit_code == 0
    assert "Error: --setup-service flag is not available" in result.output


@patch("bedrock_server_manager.api.system.enable_server_service")
def test_enable_service(mock_enable_api, runner, mock_bsm, mock_ctx):
    mock_enable_api.return_value = {"status": "success"}
    cli = click.Group("cli")
    cli.add_command(system)
    result = runner.invoke(
        cli,
        ["system", "enable-service", "--server", "test-server"],
        obj={"bsm": mock_bsm},
    )
    assert result.exit_code == 0
    assert "Service enabled successfully" in result.output
    mock_enable_api.assert_called_once_with("test-server")


@patch("bedrock_server_manager.api.system.disable_server_service")
def test_disable_service(mock_disable_api, runner, mock_bsm, mock_ctx):
    mock_disable_api.return_value = {"status": "success"}
    cli = click.Group("cli")
    cli.add_command(system)
    result = runner.invoke(
        cli,
        ["system", "disable-service", "--server", "test-server"],
        obj={"bsm": mock_bsm},
    )

    assert result.exit_code == 0
    assert "Service disabled successfully" in result.output
    mock_disable_api.assert_called_once_with("test-server")


@patch("bedrock_server_manager.api.system.get_bedrock_process_info")
@patch("time.sleep", return_value=None)
@patch("click.secho")
@patch("click.echo")
@patch("click.clear")
@patch("click.style", side_effect=lambda text, **kwargs: text)
def test_monitor_usage_success(
    mock_style,
    mock_clear,
    mock_echo,
    mock_secho,
    mock_sleep,
    mock_get_info,
    runner,
    mock_bsm,
):
    mock_get_info.side_effect = [
        {
            "status": "success",
            "process_info": {
                "pid": 1234,
                "cpu_percent": 10.5,
                "memory_mb": 256.3,
                "uptime": "01:23:45",
            },
        },
        KeyboardInterrupt,
    ]

    result = runner.invoke(
        monitor_usage, ["--server", "test-server"], obj={"bsm": mock_bsm}
    )

    assert result.exit_code == 0
    mock_secho.assert_any_call(
        "--- Monitoring Server: test-server ---", fg="magenta", bold=True
    )
    mock_echo.assert_any_call(unittest.mock.ANY)
    mock_echo.assert_any_call(unittest.mock.ANY)
    mock_echo.assert_any_call(unittest.mock.ANY)
    mock_echo.assert_any_call(unittest.mock.ANY)


@patch("bedrock_server_manager.api.system.get_bedrock_process_info")
@patch("time.sleep", return_value=None)
def test_monitor_usage_server_not_found(mock_sleep, mock_get_info, runner, mock_bsm):
    mock_get_info.side_effect = [
        {"status": "success", "process_info": None},
        KeyboardInterrupt,
    ]

    result = runner.invoke(
        monitor_usage, ["--server", "test-server"], obj={"bsm": mock_bsm}
    )

    assert result.exit_code == 0
    assert "Server process not found" in result.output


@patch("bedrock_server_manager.api.system.get_bedrock_process_info")
@patch("time.sleep", return_value=None)
def test_monitor_usage_api_error(mock_sleep, mock_get_info, runner):
    mock_get_info.side_effect = [
        {"status": "error", "message": "API Error"},
        KeyboardInterrupt,
    ]

    result = runner.invoke(monitor_usage, ["--server", "test-server"])

    assert result.exit_code == 0
    assert "Error: API Error" in result.output
