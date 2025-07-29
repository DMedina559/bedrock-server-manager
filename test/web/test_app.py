import pytest
from unittest.mock import patch, MagicMock
import os
from bedrock_server_manager.web.app import run_web_server


@pytest.fixture(autouse=True)
def setup_env_vars():
    """Set up and tear down environment variables for authentication."""
    os.environ["BEDROCK_SERVER_MANAGER_USERNAME"] = "testuser"
    os.environ["BEDROCK_SERVER_MANAGER_PASSWORD"] = "testpass"
    yield
    if "BEDROCK_SERVER_MANAGER_USERNAME" in os.environ:
        del os.environ["BEDROCK_SERVER_MANAGER_USERNAME"]
    if "BEDROCK_SERVER_MANAGER_PASSWORD" in os.environ:
        del os.environ["BEDROCK_SERVER_MANAGER_PASSWORD"]


@patch("bedrock_server_manager.web.app.uvicorn.run")
@patch("bedrock_server_manager.web.app.get_settings_instance")
def test_run_web_server_default_settings(mock_get_settings, mock_uvicorn_run):
    """Test the server runs with default settings."""
    mock_settings = MagicMock()
    mock_settings.get.side_effect = lambda key, default=None: {
        "web.port": 11325,
        "web.host": "127.0.0.1",
        "web.threads": 4,
    }.get(key, default)
    mock_get_settings.return_value = mock_settings

    run_web_server()

    mock_uvicorn_run.assert_called_once_with(
        "bedrock_server_manager.web.main:app",
        host="127.0.0.1",
        port=11325,
        log_config=mock_uvicorn_run.call_args[1]["log_config"],
        log_level="info",
        reload=False,
        workers=1,
        forwarded_allow_ips="*",
        proxy_headers=True,
    )


@patch("bedrock_server_manager.web.app.uvicorn.run")
@patch("bedrock_server_manager.web.app.get_settings_instance")
def test_run_web_server_custom_port(mock_get_settings, mock_uvicorn_run):
    """Test the server runs with a custom port."""
    mock_settings = MagicMock()
    mock_settings.get.side_effect = lambda key, default=None: {
        "web.port": 8080,
        "web.host": "127.0.0.1",
        "web.threads": 4,
    }.get(key, default)
    mock_get_settings.return_value = mock_settings

    run_web_server()

    mock_uvicorn_run.assert_called_once_with(
        "bedrock_server_manager.web.main:app",
        host="127.0.0.1",
        port=8080,
        log_config=mock_uvicorn_run.call_args[1]["log_config"],
        log_level="info",
        reload=False,
        workers=1,
        forwarded_allow_ips="*",
        proxy_headers=True,
    )


@patch("bedrock_server_manager.web.app.uvicorn.run")
@patch("bedrock_server_manager.web.app.get_settings_instance")
def test_run_web_server_invalid_port(mock_get_settings, mock_uvicorn_run):
    """Test the server uses the default port if the custom port is invalid."""
    mock_settings = MagicMock()
    mock_settings.get.side_effect = lambda key, default=None: {
        "web.port": "invalid",
        "web.host": "127.0.0.1",
        "web.threads": 4,
    }.get(key, default)
    mock_get_settings.return_value = mock_settings

    run_web_server()

    mock_uvicorn_run.assert_called_once_with(
        "bedrock_server_manager.web.main:app",
        host="127.0.0.1",
        port=11325,
        log_config=mock_uvicorn_run.call_args[1]["log_config"],
        log_level="info",
        reload=False,
        workers=1,
        forwarded_allow_ips="*",
        proxy_headers=True,
    )


@patch("bedrock_server_manager.web.app.uvicorn.run")
@patch("bedrock_server_manager.web.app.get_settings_instance")
def test_run_web_server_cli_host(mock_get_settings, mock_uvicorn_run):
    """Test the server uses the host provided via the command line."""
    mock_settings = MagicMock()
    mock_settings.get.side_effect = lambda key, default=None: {
        "web.port": 11325,
        "web.host": "127.0.0.1",
        "web.threads": 4,
    }.get(key, default)
    mock_get_settings.return_value = mock_settings

    run_web_server(host="0.0.0.0")

    mock_uvicorn_run.assert_called_once_with(
        "bedrock_server_manager.web.main:app",
        host="0.0.0.0",
        port=11325,
        log_config=mock_uvicorn_run.call_args[1]["log_config"],
        log_level="info",
        reload=False,
        workers=1,
        forwarded_allow_ips="*",
        proxy_headers=True,
    )


@patch("bedrock_server_manager.web.app.uvicorn.run")
@patch("bedrock_server_manager.web.app.get_settings_instance")
def test_run_web_server_debug_mode(mock_get_settings, mock_uvicorn_run):
    """Test the server runs in debug mode."""
    mock_settings = MagicMock()
    mock_settings.get.side_effect = lambda key, default=None: {
        "web.port": 11325,
        "web.host": "127.0.0.1",
        "web.threads": 4,
    }.get(key, default)
    mock_get_settings.return_value = mock_settings

    run_web_server(debug=True)

    mock_uvicorn_run.assert_called_once_with(
        "bedrock_server_manager.web.main:app",
        host="127.0.0.1",
        port=11325,
        log_config=mock_uvicorn_run.call_args[1]["log_config"],
        log_level="debug",
        reload=True,
        workers=1,
        forwarded_allow_ips="*",
        proxy_headers=True,
    )


@patch("bedrock_server_manager.web.app.uvicorn.run")
@patch("bedrock_server_manager.web.app.get_settings_instance")
def test_run_web_server_custom_threads(mock_get_settings, mock_uvicorn_run):
    """Test the server runs with a custom number of threads."""
    mock_settings = MagicMock()
    mock_settings.get.side_effect = lambda key, default=None: {
        "web.port": 11325,
        "web.host": "127.0.0.1",
        "web.threads": 8,
    }.get(key, default)
    mock_get_settings.return_value = mock_settings

    run_web_server()

    # Note: the `workers` argument in uvicorn.run is now set to 1 and not threads
    # this is because of the line `workers=1,  # workers if not reload_enabled and workers > 1 else None,`
    mock_uvicorn_run.assert_called_once_with(
        "bedrock_server_manager.web.main:app",
        host="127.0.0.1",
        port=11325,
        log_config=mock_uvicorn_run.call_args[1]["log_config"],
        log_level="info",
        reload=False,
        workers=1,
        forwarded_allow_ips="*",
        proxy_headers=True,
    )


@patch("bedrock_server_manager.web.app.uvicorn.run")
@patch("bedrock_server_manager.web.app.get_settings_instance")
def test_run_web_server_invalid_threads(mock_get_settings, mock_uvicorn_run):
    """Test the server uses the default number of threads if the custom number is invalid."""
    mock_settings = MagicMock()
    mock_settings.get.side_effect = lambda key, default=None: {
        "web.port": 11325,
        "web.host": "127.0.0.1",
        "web.threads": "invalid",
    }.get(key, default)
    mock_get_settings.return_value = mock_settings

    run_web_server()

    mock_uvicorn_run.assert_called_once_with(
        "bedrock_server_manager.web.main:app",
        host="127.0.0.1",
        port=11325,
        log_config=mock_uvicorn_run.call_args[1]["log_config"],
        log_level="info",
        reload=False,
        workers=1,
        forwarded_allow_ips="*",
        proxy_headers=True,
    )
