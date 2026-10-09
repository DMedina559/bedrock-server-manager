from unittest.mock import MagicMock

import pytest

from bedrock_server_manager.web.main import run_web_server


def test_run_web_server_default_config(app_context, monkeypatch):
    """Test run_web_server uses default config if none provided."""
    mock_run = MagicMock()
    monkeypatch.setattr("uvicorn.Server.run", mock_run)

    run_web_server(app_context)

    mock_run.assert_called_once()
    # Check config that was passed to Server
    server_instance = app_context._web_server
    assert server_instance.config.host == "127.0.0.1"
    assert server_instance.config.port == 11325
    assert server_instance.config.log_level is None
    assert server_instance.config.reload is False


async def test_run_web_server_cli_args(app_context, monkeypatch):
    """Test run_web_server prefers CLI args over settings."""
    mock_run = MagicMock()
    monkeypatch.setattr("uvicorn.Server.run", mock_run)

    await app_context.settings.set("web.host", "10.0.0.1")
    await app_context.settings.set("web.port", 8080)

    run_web_server(app_context, host="192.168.1.1", port=9000, debug=True)

    server_instance = app_context._web_server
    assert server_instance.config.host == "192.168.1.1"
    assert server_instance.config.port == 9000
    assert server_instance.config.log_level is None
    assert server_instance.config.reload is True


def test_run_web_server_invalid_host_type(app_context, monkeypatch):
    """Test run_web_server raises ValueError for non-string host."""
    with pytest.raises(ValueError, match="Host must be a string"):
        run_web_server(app_context, host=123)


async def test_run_web_server_invalid_port_setting(app_context, monkeypatch):
    """Invalid persisted settings are rejected before web startup."""
    mock_run = MagicMock()
    monkeypatch.setattr("uvicorn.Server.run", mock_run)

    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        await app_context.settings.set("web.port", "invalid")

    run_web_server(app_context)

    server_instance = app_context._web_server
    assert server_instance.config.port == 11325


def test_run_web_server_exception_propagation(app_context, monkeypatch):
    """Test run_web_server logs and re-raises exceptions during startup."""
    mock_run = MagicMock(side_effect=RuntimeError("Server crashed"))
    monkeypatch.setattr("uvicorn.Server.run", mock_run)

    with pytest.raises(RuntimeError, match="Server crashed"):
        run_web_server(app_context)


def test_web_logging_respects_verbosity_and_preserves_host_handlers(
    app_context, monkeypatch, caplog
):
    import logging

    logger = logging.getLogger("uvicorn.access")
    handler = logging.NullHandler()
    logger.addHandler(handler)
    monkeypatch.setattr("uvicorn.Server.run", MagicMock())
    try:
        with caplog.at_level(logging.INFO):
            run_web_server(app_context)
            logger.info("GET /health 200")
            logging.getLogger("uvicorn.error").info("connection open")
            logging.getLogger("uvicorn.error").warning("WebSocket rejected")
        assert not any(
            "GET /health" in record.message or record.message == "connection open"
            for record in caplog.records
        )
        assert any(record.message == "WebSocket rejected" for record in caplog.records)
        with caplog.at_level(logging.DEBUG):
            run_web_server(app_context)
            logger.info("GET /health 200")
        assert handler in logger.handlers
        assert logger.propagate
        assert any(
            record.message == "GET /health 200" and record.levelno == logging.DEBUG
            for record in caplog.records
        )
    finally:
        logger.removeHandler(handler)
