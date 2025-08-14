import os
from unittest.mock import MagicMock, patch

import pytest

from bedrock_server_manager.web.main import run_web_server


def test_run_web_server_default_settings(mocker, app_context):
    """Test the server runs with default settings."""
    mock_uvicorn_run = mocker.patch("bedrock_server_manager.web.main.uvicorn.run")
    mocker.patch.object(
        app_context.settings,
        "get",
        side_effect=lambda key, default=None: {
            "web.port": 11325,
            "web.host": "127.0.0.1",
            "web.threads": 4,
            "paths.plugins": "/tmp/plugins",
            "paths.themes": "/tmp/themes",
        }.get(key, default),
    )

    run_web_server(app_context)

    mock_uvicorn_run.assert_called_once()
    args, kwargs = mock_uvicorn_run.call_args
    assert kwargs["host"] == "127.0.0.1"
    assert kwargs["port"] == 11325
    assert kwargs["log_level"] == "info"
    assert not kwargs["reload"]


def test_run_web_server_custom_port(mocker, app_context):
    """Test the server runs with a custom port."""
    mock_uvicorn_run = mocker.patch("bedrock_server_manager.web.main.uvicorn.run")
    mocker.patch.object(
        app_context.settings,
        "get",
        side_effect=lambda key, default=None: {
            "web.port": 8080,
            "web.host": "127.0.0.1",
            "web.threads": 4,
            "paths.plugins": "/tmp/plugins",
            "paths.themes": "/tmp/themes",
        }.get(key, default),
    )

    run_web_server(app_context)

    mock_uvicorn_run.assert_called_once()
    args, kwargs = mock_uvicorn_run.call_args
    assert kwargs["port"] == 8080


def test_run_web_server_invalid_port(mocker, app_context):
    """Test the server uses the default port if the custom port is invalid."""
    mock_uvicorn_run = mocker.patch("bedrock_server_manager.web.main.uvicorn.run")
    mocker.patch.object(
        app_context.settings,
        "get",
        side_effect=lambda key, default=None: {
            "web.port": "invalid",
            "web.host": "127.0.0.1",
            "web.threads": 4,
            "paths.plugins": "/tmp/plugins",
            "paths.themes": "/tmp/themes",
        }.get(key, default),
    )

    run_web_server(app_context)

    mock_uvicorn_run.assert_called_once()
    args, kwargs = mock_uvicorn_run.call_args
    assert kwargs["port"] == 11325


def test_run_web_server_cli_host(mocker, app_context):
    """Test the server uses the host provided via the command line."""
    mock_uvicorn_run = mocker.patch("bedrock_server_manager.web.main.uvicorn.run")
    mocker.patch.object(
        app_context.settings,
        "get",
        side_effect=lambda key, default=None: {
            "web.port": 11325,
            "web.host": "127.0.0.1",
            "web.threads": 4,
            "paths.plugins": "/tmp/plugins",
            "paths.themes": "/tmp/themes",
        }.get(key, default),
    )

    run_web_server(app_context, host="0.0.0.0")

    mock_uvicorn_run.assert_called_once()
    args, kwargs = mock_uvicorn_run.call_args
    assert kwargs["host"] == "0.0.0.0"


def test_run_web_server_debug_mode(mocker, app_context):
    """Test the server runs in debug mode."""
    mock_uvicorn_run = mocker.patch("bedrock_server_manager.web.main.uvicorn.run")
    mocker.patch.object(
        app_context.settings,
        "get",
        side_effect=lambda key, default=None: {
            "web.port": 11325,
            "web.host": "127.0.0.1",
            "web.threads": 4,
            "paths.plugins": "/tmp/plugins",
            "paths.themes": "/tmp/themes",
        }.get(key, default),
    )

    run_web_server(app_context, debug=True)

    mock_uvicorn_run.assert_called_once()
    args, kwargs = mock_uvicorn_run.call_args
    assert kwargs["log_level"] == "debug"
    assert kwargs["reload"]


def test_run_web_server_custom_threads(mocker, app_context):
    """Test the server runs with a custom number of threads."""
    mock_uvicorn_run = mocker.patch("bedrock_server_manager.web.main.uvicorn.run")
    mocker.patch.object(
        app_context.settings,
        "get",
        side_effect=lambda key, default=None: {
            "web.port": 11325,
            "web.host": "127.0.0.1",
            "web.threads": 8,
            "paths.plugins": "/tmp/plugins",
            "paths.themes": "/tmp/themes",
        }.get(key, default),
    )

    run_web_server(app_context)

    mock_uvicorn_run.assert_called_once()
    args, kwargs = mock_uvicorn_run.call_args
    assert kwargs["workers"] == 1


def test_run_web_server_invalid_threads(mocker, app_context):
    """Test the server uses the default number of threads if the custom number is invalid."""
    mock_uvicorn_run = mocker.patch("bedrock_server_manager.web.main.uvicorn.run")
    mocker.patch.object(
        app_context.settings,
        "get",
        side_effect=lambda key, default=None: {
            "web.port": 11325,
            "web.host": "127.0.0.1",
            "web.threads": "invalid",
            "paths.plugins": "/tmp/plugins",
            "paths.themes": "/tmp/themes",
        }.get(key, default),
    )

    run_web_server(app_context)

    mock_uvicorn_run.assert_called_once()
    args, kwargs = mock_uvicorn_run.call_args
    assert kwargs["workers"] == 1
