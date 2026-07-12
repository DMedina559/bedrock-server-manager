from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from bedrock_server_manager.cli.web import web
from bedrock_server_manager.error import BSMError


@pytest.fixture
def runner():
    return CliRunner()


def test_start_web_server_direct_success(runner, app_context, monkeypatch):
    """Test start web server CLI command successfully running in direct mode."""
    mock_api = MagicMock(return_value={"status": "success"})
    monkeypatch.setattr("bedrock_server_manager.api.web.start_web_server_api", mock_api)

    result = runner.invoke(
        web, ["start", "--mode", "direct"], obj={"app_context": app_context}
    )

    assert result.exit_code == 0
    assert "Attempting to start web server in 'direct' mode..." in result.output
    mock_api.assert_called_once_with(
        host=None, port=None, debug=False, mode="direct", app_context=app_context
    )


def test_start_web_server_detached_success(runner, app_context, monkeypatch):
    """Test start web server CLI command successfully running in detached mode."""
    mock_api = MagicMock(return_value={"status": "success", "pid": 1234})
    monkeypatch.setattr("bedrock_server_manager.api.web.start_web_server_api", mock_api)

    result = runner.invoke(
        web,
        ["start", "--mode", "detached", "-H", "0.0.0.0", "-p", "8080"],
        obj={"app_context": app_context},
    )

    assert result.exit_code == 0
    assert "PID: 1234" in result.output
    mock_api.assert_called_once_with(
        host="0.0.0.0", port=8080, debug=False, mode="detached", app_context=app_context
    )


def test_start_web_server_detached_error(runner, app_context, monkeypatch):
    """Test start web server CLI command failing in detached mode returns abort."""
    mock_api = MagicMock(return_value={"status": "error", "message": "Port in use"})
    monkeypatch.setattr("bedrock_server_manager.api.web.start_web_server_api", mock_api)

    result = runner.invoke(
        web, ["start", "--mode", "detached"], obj={"app_context": app_context}
    )

    assert result.exit_code == 1  # Abort
    assert "Error: Port in use" in result.output


def test_start_web_server_exception(runner, app_context, monkeypatch):
    """Test start web server CLI command catches application exceptions and aborts."""

    def mock_raise(*args, **kwargs):
        raise BSMError("Critical failure")

    monkeypatch.setattr(
        "bedrock_server_manager.api.web.start_web_server_api", mock_raise
    )

    result = runner.invoke(
        web, ["start", "--mode", "direct"], obj={"app_context": app_context}
    )

    assert result.exit_code == 1  # Abort
    assert "Failed to start web server: Critical failure" in result.output


def test_stop_web_server_success(runner, app_context, monkeypatch):
    """Test stop web server CLI command successfully running."""
    mock_api = MagicMock(return_value={"status": "success", "message": "Stopped"})
    monkeypatch.setattr("bedrock_server_manager.api.web.stop_web_server_api", mock_api)

    result = runner.invoke(web, ["stop"], obj={"app_context": app_context})

    assert result.exit_code == 0
    assert "Success: Stopped" in result.output
    mock_api.assert_called_once()


def test_stop_web_server_error(runner, app_context, monkeypatch):
    """Test stop web server CLI command catching application errors and aborts."""

    def mock_raise(*args, **kwargs):
        raise BSMError("Could not stop")

    monkeypatch.setattr(
        "bedrock_server_manager.api.web.stop_web_server_api", mock_raise
    )

    result = runner.invoke(web, ["stop"], obj={"app_context": app_context})

    assert result.exit_code == 1  # Abort
    assert "An error occurred: Could not stop" in result.output
