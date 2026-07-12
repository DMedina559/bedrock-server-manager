from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from bedrock_server_manager.cli.service import (
    configure_web_service,
    disable_web_service_cli,
    enable_web_service_cli,
    remove_web_service_cli,
    status_web_service_cli,
)


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture(autouse=True)
def mock_service_manager_check(monkeypatch):
    """Bypasses @requires_web_service_manager decorator check for testing"""
    monkeypatch.setattr(
        "bedrock_server_manager.cli.service.can_manage_services", lambda: True
    )


def test_configure_web_service_interactive(runner, app_context, monkeypatch):
    """Test configure service command launches interactive workflow when no flags passed."""
    mock_workflow = MagicMock()
    monkeypatch.setattr(
        "bedrock_server_manager.cli.service.interactive_web_service_workflow",
        mock_workflow,
    )

    result = runner.invoke(configure_web_service, obj={"app_context": app_context})
    assert result.exit_code == 0
    assert "starting interactive Web UI service setup" in result.output
    mock_workflow.assert_called_once()


def test_configure_web_service_flags(runner, app_context, monkeypatch):
    """Test configure service command skips interactive prompts if config flags are given."""
    mock_perform = MagicMock()
    monkeypatch.setattr(
        "bedrock_server_manager.cli.service._perform_web_service_configuration",
        mock_perform,
    )

    result = runner.invoke(
        configure_web_service, ["--setup-service"], obj={"app_context": app_context}
    )
    assert result.exit_code == 0
    assert "Web UI configuration applied successfully." in result.output
    mock_perform.assert_called_once()


def test_enable_web_service_cli(runner, app_context, monkeypatch):
    """Test enable service command successfully queries the web api."""
    mock_api = MagicMock(return_value={"status": "success"})
    monkeypatch.setattr(
        "bedrock_server_manager.api.web.enable_web_ui_service", mock_api
    )

    result = runner.invoke(enable_web_service_cli, obj={"app_context": app_context})
    assert result.exit_code == 0
    assert "Web UI service enabled successfully" in result.output


def test_disable_web_service_cli(runner, app_context, monkeypatch):
    """Test disable service command successfully queries the web api."""
    mock_api = MagicMock(return_value={"status": "success"})
    monkeypatch.setattr(
        "bedrock_server_manager.api.web.disable_web_ui_service", mock_api
    )

    result = runner.invoke(disable_web_service_cli, obj={"app_context": app_context})
    assert result.exit_code == 0


def test_remove_web_service_cli_confirm_yes(runner, app_context, monkeypatch):
    """Test remove service command drops the service after confirming yes."""
    mock_questionary = MagicMock()
    mock_questionary.confirm().ask.return_value = True
    monkeypatch.setattr(
        "bedrock_server_manager.cli.service.questionary", mock_questionary
    )

    mock_api = MagicMock(return_value={"status": "success"})
    monkeypatch.setattr(
        "bedrock_server_manager.api.web.remove_web_ui_service", mock_api
    )

    result = runner.invoke(remove_web_service_cli, obj={"app_context": app_context})
    assert result.exit_code == 0
    mock_api.assert_called_once()


def test_remove_web_service_cli_confirm_no(runner, app_context, monkeypatch):
    """Test remove service command skips drop when declining the confirmation prompt."""
    mock_questionary = MagicMock()
    mock_questionary.confirm().ask.return_value = False
    monkeypatch.setattr(
        "bedrock_server_manager.cli.service.questionary", mock_questionary
    )

    mock_api = MagicMock()
    monkeypatch.setattr(
        "bedrock_server_manager.api.web.remove_web_ui_service", mock_api
    )

    result = runner.invoke(remove_web_service_cli, obj={"app_context": app_context})
    assert result.exit_code == 0
    assert "Removal cancelled" in result.output
    mock_api.assert_not_called()


def test_status_web_service_cli(runner, app_context, monkeypatch):
    """Test status service command prints out correctly formatted info."""
    mock_api = MagicMock(
        return_value={
            "status": "success",
            "service_exists": True,
            "is_active": True,
            "is_enabled": False,
            "message": "All good",
        }
    )
    monkeypatch.setattr(
        "bedrock_server_manager.api.web.get_web_ui_service_status", mock_api
    )

    result = runner.invoke(status_web_service_cli, obj={"app_context": app_context})
    assert result.exit_code == 0
    assert "Web UI Service Status:" in result.output
    assert "Currently Active (Running): True" in result.output
    assert "Enabled for Autostart: False" in result.output
    assert "All good" in result.output
