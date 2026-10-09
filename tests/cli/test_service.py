from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from bedrock_server_manager.cli.service import service
from bedrock_server_manager.core import service as service_core


def invoke(app_context, *args):
    return CliRunner().invoke(service, args, obj={"app_context": app_context})


@pytest.mark.parametrize("system", [False, True])
@pytest.mark.parametrize("autostart", [False, True])
def test_configure_service_flags_write_real_unit(
    app_context, systemd, system, autostart
):
    systemd.enabled = True
    flags = [
        "--setup-service",
        "--enable-autostart" if autostart else "--no-enable-autostart",
    ]
    if system:
        flags.append("--system")
    result = invoke(app_context, "configure", *flags)
    assert result.exit_code == 0, result.output
    assert "configuration applied successfully" in result.output
    unit = systemd.path(system).read_text()
    assert f"WorkingDirectory={app_context.data_dir}" in unit
    assert "-m bedrock_server_manager web start --mode direct" in unit
    assert "-m bedrock_server_manager web stop" in unit
    assert "Type=simple" in unit
    assert systemd.enabled is autostart
    assert all(("--user" not in command) == system for command in systemd.commands)


def test_interactive_service_setup_executes_real_workflow(
    app_context, systemd, monkeypatch
):
    questions = MagicMock()
    questions.confirm().ask.side_effect = [True, False, True]
    monkeypatch.setattr("bedrock_server_manager.cli.service.questionary", questions)
    result = invoke(app_context, "configure")
    assert result.exit_code == 0, result.output
    assert "service configuration complete" in result.output
    assert systemd.path().is_file()
    assert systemd.enabled
    assert any("enable" in command for command in systemd.commands)


@pytest.mark.parametrize("system", [False, True])
def test_service_cli_lifecycle_uses_real_api_and_service_manager(
    app_context, systemd, monkeypatch, system
):
    flags = ["--system"] if system else []
    result = invoke(
        app_context, "configure", "--setup-service", "--enable-autostart", *flags
    )
    assert result.exit_code == 0, result.output
    assert systemd.enabled
    result = invoke(app_context, "disable", *flags)
    assert result.exit_code == 0, result.output
    assert "disabled successfully" in result.output
    assert not systemd.enabled
    result = invoke(app_context, "enable", *flags)
    assert result.exit_code == 0, result.output
    assert "enabled successfully" in result.output
    assert systemd.enabled
    systemd.active = True
    result = invoke(app_context, "status", *flags)
    assert result.exit_code == 0, result.output
    assert "Service Defined: True" in result.output
    assert "Currently Active (Running): True" in result.output
    assert "Enabled for Autostart: True" in result.output
    questions = MagicMock()
    questions.confirm().ask.return_value = True
    monkeypatch.setattr("bedrock_server_manager.cli.service.questionary", questions)
    result = invoke(app_context, "remove", *flags)
    assert result.exit_code == 0, result.output
    assert "removed successfully" in result.output
    assert not systemd.path(system).exists()
    result = invoke(app_context, "status", *flags)
    assert result.exit_code == 0, result.output
    assert "Service Defined: False" in result.output
    assert all(("--user" not in command) == system for command in systemd.commands)


def test_remove_service_declined_keeps_unit_and_makes_no_os_calls(
    app_context, systemd, monkeypatch
):
    invoke(app_context, "configure", "--setup-service", "--enable-autostart")
    original = systemd.path().read_bytes()
    systemd.commands.clear()
    questions = MagicMock()
    questions.confirm().ask.return_value = False
    monkeypatch.setattr("bedrock_server_manager.cli.service.questionary", questions)
    result = invoke(app_context, "remove")
    assert result.exit_code == 0
    assert "Removal cancelled" in result.output
    assert systemd.path().read_bytes() == original
    assert not systemd.commands


def test_service_command_reports_real_os_failure(app_context, systemd):
    invoke(app_context, "configure", "--setup-service", "--no-enable-autostart")
    systemd.failure = "enable"
    result = invoke(app_context, "enable")
    assert result.exit_code == 1
    assert "Failed to enable Web UI service" in result.output
    assert not systemd.enabled
    assert systemd.path().is_file()


def test_service_command_rejects_missing_service_manager(
    app_context, systemd, monkeypatch
):
    monkeypatch.setattr(service_core.shutil, "which", lambda cmd: None)
    result = invoke(app_context, "enable")
    assert result.exit_code == 1
    assert "service manager" in result.output
    assert not systemd.commands
