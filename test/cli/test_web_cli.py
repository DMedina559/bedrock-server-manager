import unittest
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from bedrock_server_manager.cli.web import start_web_server, stop_web_server


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def mock_app_context():
    app_context = MagicMock()
    app_context.bsm.can_manage_services = True
    app_context.bsm.get_os_type.return_value = "Linux"
    return app_context


@pytest.fixture
def mock_ctx(mock_app_context):
    ctx = MagicMock()
    ctx.obj = {"app_context": mock_app_context, "bsm": MagicMock(), "cli": MagicMock()}
    return ctx


@patch("bedrock_server_manager.api.web.start_web_server_api")
def test_start_web_server_direct(mock_start_api, runner, mock_ctx):
    mock_start_api.return_value = {"status": "success"}
    result = runner.invoke(start_web_server, ["--mode", "direct"], obj=mock_ctx.obj)

    assert result.exit_code == 0
    assert "Server will run in this terminal" in result.output
    mock_start_api.assert_called_once_with(
        host=None,
        port=None,
        debug=False,
        mode="direct",
        app_context=mock_ctx.obj["app_context"],
    )


@patch("bedrock_server_manager.api.web.start_web_server_api")
def test_start_web_server_detached(mock_start_api, runner, mock_ctx):
    mock_start_api.return_value = {"status": "success", "pid": 1234}
    result = runner.invoke(start_web_server, ["--mode", "detached"], obj=mock_ctx.obj)

    assert result.exit_code == 0
    assert "Web server start initiated in detached mode" in result.output
    mock_start_api.assert_called_once_with(
        host=None,
        port=None,
        debug=False,
        mode="detached",
        app_context=mock_ctx.obj["app_context"],
    )


@patch("bedrock_server_manager.api.web.stop_web_server_api")
def test_stop_web_server(mock_stop_api, runner, mock_ctx):
    mock_stop_api.return_value = {"status": "success"}
    result = runner.invoke(stop_web_server, obj=mock_ctx.obj)

    assert result.exit_code == 0
    assert "Web server stopped successfully" in result.output
    mock_stop_api.assert_called_once_with(app_context=mock_ctx.obj["app_context"])
