from unittest.mock import AsyncMock

import pytest
from click.testing import CliRunner

from bedrock_server_manager.cli.web import web
from bedrock_server_manager.error import BSMError
from bedrock_server_manager.web.process import WebProcessPaths
from bedrock_server_manager.web.runtime import WebRunOptions


@pytest.fixture
def runner():
    return CliRunner()


def test_start_web_server_direct_success(runner, app_context, monkeypatch):
    servers = []

    def run(server):
        server.started = True
        servers.append(server)

    monkeypatch.setattr("uvicorn.Server.run", run)
    result = runner.invoke(
        web,
        ["start", "--mode", "direct", "-H", "127.0.0.1", "-p", "8080"],
        obj={"app_context": app_context},
    )
    assert result.exit_code == 0
    assert "Attempting to start web server in 'direct' mode..." in result.output
    assert len(servers) == 1
    server = servers[0]
    assert server.config.host == "127.0.0.1"
    assert server.config.port == 8080
    assert server.config.app.state.app_context is app_context


def test_start_web_server_detached_success(runner, app_context, monkeypatch):
    """Test start web server CLI command successfully running in detached mode."""
    mock_api = AsyncMock(return_value=1234)
    monkeypatch.setattr("bedrock_server_manager.cli.web.start_detached", mock_api)

    result = runner.invoke(
        web,
        ["start", "--mode", "detached", "-H", "0.0.0.0", "-p", "8080"],
        obj={"app_context": app_context},
    )

    assert result.exit_code == 0
    assert "PID: 1234" in result.output
    mock_api.assert_awaited_once_with(
        WebProcessPaths(
            config_dir=app_context.config_dir,
            data_dir=app_context.data_dir,
            db_url=app_context.db_url,
        ),
        WebRunOptions(host="0.0.0.0", port=8080),
    )


def test_start_web_server_detached_error(runner, app_context, monkeypatch):
    """Test start web server CLI command failing in detached mode returns abort."""
    mock_api = AsyncMock(side_effect=BSMError("Port in use"))
    monkeypatch.setattr("bedrock_server_manager.cli.web.start_detached", mock_api)

    result = runner.invoke(
        web, ["start", "--mode", "detached"], obj={"app_context": app_context}
    )

    assert result.exit_code == 1  # Abort
    assert "Port in use" in result.output


def test_start_web_server_exception(runner, app_context, monkeypatch):
    """Test start web server CLI command catches application exceptions and aborts."""

    def mock_raise(*args, **kwargs):
        raise BSMError("Critical failure")

    monkeypatch.setattr("bedrock_server_manager.cli.web.run_web_server", mock_raise)

    result = runner.invoke(
        web, ["start", "--mode", "direct"], obj={"app_context": app_context}
    )

    assert result.exit_code == 1  # Abort
    assert "Failed to start web server: Critical failure" in result.output


def test_stop_web_server_success(runner, app_context):
    result = runner.invoke(web, ["stop"], obj={"app_context": app_context})
    assert result.exit_code == 0
    assert "Web server not running" in result.output


def test_stop_web_server_error(runner, app_context, monkeypatch):
    """Test stop web server CLI command catching application errors and aborts."""

    async def mock_raise(*args, **kwargs):
        raise BSMError("Could not stop")

    monkeypatch.setattr("bedrock_server_manager.cli.web.stop_local", mock_raise)

    result = runner.invoke(web, ["stop"], obj={"app_context": app_context})

    assert result.exit_code == 1  # Abort
    assert "Failed to stop web server: Could not stop" in result.output
