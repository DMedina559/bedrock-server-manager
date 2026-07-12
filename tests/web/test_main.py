from unittest.mock import MagicMock

import pytest

from bedrock_server_manager.web.main import run_web_server


def test_run_web_server_default_config(app_context, monkeypatch):
    """Test run_web_server uses default config if none provided."""
    mock_run = MagicMock()
    monkeypatch.setattr("uvicorn.Server.run", mock_run)

    # Needs to bypass actual application creation because it loads routers
    # we just mock create_web_app here since it's already tested
    monkeypatch.setattr("bedrock_server_manager.web.main.create_web_app", MagicMock())

    run_web_server(app_context)

    mock_run.assert_called_once()
    # Check config that was passed to Server
    server_instance = app_context._web_server
    assert server_instance.config.host == "127.0.0.1"
    assert server_instance.config.port == 11325
    assert server_instance.config.log_level == "info"
    assert server_instance.config.reload is False


def test_run_web_server_cli_args(app_context, monkeypatch):
    """Test run_web_server prefers CLI args over settings."""
    mock_run = MagicMock()
    monkeypatch.setattr("uvicorn.Server.run", mock_run)
    monkeypatch.setattr("bedrock_server_manager.web.main.create_web_app", MagicMock())

    app_context.settings.set("web.host", "10.0.0.1")
    app_context.settings.set("web.port", 8080)

    run_web_server(app_context, host="192.168.1.1", port=9000, debug=True)

    server_instance = app_context._web_server
    assert server_instance.config.host == "192.168.1.1"
    assert server_instance.config.port == 9000
    assert server_instance.config.log_level == "debug"
    assert server_instance.config.reload is True


def test_run_web_server_invalid_host_type(app_context, monkeypatch):
    """Test run_web_server raises ValueError for non-string host."""
    with pytest.raises(ValueError, match="Host must be a string"):
        run_web_server(app_context, host=123)


def test_run_web_server_invalid_port_setting(app_context, monkeypatch):
    """Test run_web_server falls back to default port if setting is invalid."""
    mock_run = MagicMock()
    monkeypatch.setattr("uvicorn.Server.run", mock_run)
    monkeypatch.setattr("bedrock_server_manager.web.main.create_web_app", MagicMock())

    app_context.settings.set("web.port", "invalid")

    run_web_server(app_context)

    server_instance = app_context._web_server
    assert server_instance.config.port == 11325


def test_run_web_server_exception_propagation(app_context, monkeypatch):
    """Test run_web_server logs and re-raises exceptions during startup."""
    mock_run = MagicMock(side_effect=RuntimeError("Server crashed"))
    monkeypatch.setattr("uvicorn.Server.run", mock_run)
    monkeypatch.setattr("bedrock_server_manager.web.main.create_web_app", MagicMock())

    with pytest.raises(RuntimeError, match="Server crashed"):
        run_web_server(app_context)
