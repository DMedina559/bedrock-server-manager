import shlex
from unittest.mock import MagicMock

import pytest

from bedrock_server_manager.cli.service import service


@pytest.fixture
def invoke(app_context, runner):
    def run(*args):
        return runner.invoke(service, args, obj={"app_context": app_context})

    return run


@pytest.mark.parametrize("system", [False, True])
@pytest.mark.parametrize("autostart", [False, True])
def test_configure_service_flags_write_real_unit(
    invoke, app_context, systemd, system, autostart
):
    systemd.enabled = True
    flags = [
        "--setup-service",
        "--enable-autostart" if autostart else "--no-enable-autostart",
    ]
    if system:
        flags.append("--system")
    result = invoke("configure", *flags)
    assert result.exit_code == 0, result.output
    assert "configuration applied successfully" in result.output
    unit = systemd.path(system).read_text()
    assert f"WorkingDirectory={app_context.data_dir}" in unit
    assert "web start --mode direct" in unit
    command = next(
        line.removeprefix("ExecStart=")
        for line in unit.splitlines()
        if line.startswith("ExecStart=")
    )
    arguments = shlex.split(command.replace("%%", "%"))
    assert arguments[arguments.index("--config-dir") + 1] == app_context.config_dir
    assert arguments[arguments.index("--data-dir") + 1] == app_context.data_dir
    assert "ExecStop=" not in unit
    assert "Restart=on-failure" in unit
    assert "TimeoutStopSec=180s" in unit
    assert "Type=simple" in unit
    assert systemd.enabled is autostart
    assert all(("--user" not in command) == system for command in systemd.commands)


def test_interactive_service_setup_executes_real_workflow(invoke, systemd, monkeypatch):
    questions = MagicMock()
    questions.confirm().ask.side_effect = [True, False, True]
    monkeypatch.setattr("bedrock_server_manager.cli.service.questionary", questions)
    result = invoke("configure")
    assert result.exit_code == 0, result.output
    assert "service configuration complete" in result.output
    assert systemd.path().is_file()
    assert systemd.enabled
    assert any("enable" in command for command in systemd.commands)


@pytest.mark.parametrize("system", [False, True])
def test_service_cli_lifecycle_uses_real_api_and_service_manager(
    invoke, systemd, monkeypatch, system
):
    flags = ["--system"] if system else []
    result = invoke("configure", "--setup-service", "--enable-autostart", *flags)
    assert result.exit_code == 0, result.output
    assert systemd.enabled
    result = invoke("disable", *flags)
    assert result.exit_code == 0, result.output
    assert "disabled successfully" in result.output
    assert not systemd.enabled
    result = invoke("enable", *flags)
    assert result.exit_code == 0, result.output
    assert "enabled successfully" in result.output
    assert systemd.enabled
    systemd.active = True
    result = invoke("status", *flags)
    assert result.exit_code == 0, result.output
    assert "Service Defined: True" in result.output
    assert "Currently Active (Running): True" in result.output
    assert "Enabled for Autostart: True" in result.output
    questions = MagicMock()
    questions.confirm().ask.return_value = True
    monkeypatch.setattr("bedrock_server_manager.cli.service.questionary", questions)
    result = invoke("remove", *flags)
    assert result.exit_code == 0, result.output
    assert "removed successfully" in result.output
    assert not systemd.path(system).exists()
    result = invoke("status", *flags)
    assert result.exit_code == 0, result.output
    assert "Service Defined: False" in result.output
    assert all(("--user" not in command) == system for command in systemd.commands)


def test_remove_service_declined_keeps_unit_and_makes_no_os_calls(
    invoke, systemd, monkeypatch
):
    invoke("configure", "--setup-service", "--enable-autostart")
    original = systemd.path().read_bytes()
    systemd.commands.clear()
    questions = MagicMock()
    questions.confirm().ask.return_value = False
    monkeypatch.setattr("bedrock_server_manager.cli.service.questionary", questions)
    result = invoke("remove")
    assert result.exit_code == 0
    assert "Removal cancelled" in result.output
    assert systemd.path().read_bytes() == original
    assert not systemd.commands


def test_service_command_reports_real_os_failure(invoke, systemd):
    invoke("configure", "--setup-service", "--no-enable-autostart")
    systemd.failure = "enable"
    result = invoke("enable")
    assert result.exit_code == 1
    assert "Failed to enable Web UI service" in result.output
    assert not systemd.enabled
    assert systemd.path().is_file()


def test_service_command_rejects_missing_service_manager(invoke, systemd):
    systemd.available = False
    result = invoke("enable")
    assert result.exit_code == 1
    assert "service manager" in result.output
    assert not systemd.commands
