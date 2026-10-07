from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from bedrock_server_manager.api.models import (
    GetBedrockProcessInfoRequest,
    GetServerRunningStatusRequest,
)
from bedrock_server_manager.api.system import (
    get_bedrock_process_info,
    get_server_running_status,
)


async def test_get_server_running_status_success(app_context, monkeypatch):
    """Test get_server_running_status correctly parses and returns truthy value."""
    mock_server = MagicMock()
    mock_server.is_running = AsyncMock()
    mock_server.get_process_info = AsyncMock()
    mock_server.is_running.return_value = True
    monkeypatch.setattr(app_context, "get_server", lambda x: mock_server)

    result = (
        await get_server_running_status(
            request=GetServerRunningStatusRequest(server_name="test_server"),
            app_context=app_context,
        )
    ).model_dump(mode="python")

    assert result["status"] == "success"
    assert result["is_running"] is True


async def test_get_server_running_status_missing_name(app_context):
    """Test get_server_running_status throws correctly on missing server argument."""
    with pytest.raises(ValidationError):
        (
            await get_server_running_status(
                request=GetServerRunningStatusRequest(server_name=""),
                app_context=app_context,
            )
        ).model_dump(mode="python")


async def test_get_server_running_status_error(app_context, monkeypatch):
    """Test get_server_running_status wraps specific core exceptions appropriately."""

    def throw_err(*args):
        raise Exception("System query error")

    monkeypatch.setattr(app_context, "get_server", throw_err)

    with pytest.raises(Exception):
        (
            await get_server_running_status(
                request=GetServerRunningStatusRequest(server_name="test_server"),
                app_context=app_context,
            )
        ).model_dump(mode="python")


async def test_get_bedrock_process_info_success(app_context, monkeypatch):
    """Test get_bedrock_process_info returns a well-formed process dict when active."""
    mock_server = MagicMock()
    mock_server.is_running = AsyncMock()
    mock_server.get_process_info = AsyncMock()
    mock_server.get_process_info.return_value = {
        "pid": 1234,
        "cpu_percent": 12.0,
        "memory_mb": 42.0,
        "uptime": "0:01:00",
    }
    monkeypatch.setattr(app_context, "get_server", lambda x: mock_server)

    result = (
        await get_bedrock_process_info(
            request=GetBedrockProcessInfoRequest(server_name="test_server"),
            app_context=app_context,
        )
    ).model_dump(mode="python")

    assert result["status"] == "success"
    assert result["process_info"]["pid"] == 1234
    assert result["process_info"]["cpu_percent"] == 12.0


async def test_get_bedrock_process_info_not_running(app_context, monkeypatch):
    """Test get_bedrock_process_info handles None gracefully signifying not running."""
    mock_server = MagicMock()
    mock_server.is_running = AsyncMock()
    mock_server.get_process_info = AsyncMock()
    mock_server.get_process_info.return_value = None
    monkeypatch.setattr(app_context, "get_server", lambda x: mock_server)

    result = (
        await get_bedrock_process_info(
            request=GetBedrockProcessInfoRequest(server_name="test_server"),
            app_context=app_context,
        )
    ).model_dump(mode="python")

    assert result["status"] == "success"
    assert result["process_info"] is None
    assert "not found" in result["message"]


async def test_get_bedrock_process_info_missing_name(app_context):
    """Test get_bedrock_process_info correctly fails when empty name is passed."""
    with pytest.raises(ValidationError):
        (
            await get_bedrock_process_info(
                request=GetBedrockProcessInfoRequest(server_name=""),
                app_context=app_context,
            )
        ).model_dump(mode="python")


async def test_get_bedrock_process_info_error(app_context, monkeypatch):
    """Test get_bedrock_process_info catches arbitrary exception formats correctly."""

    def throw_err(*args):
        raise Exception("Access failure")

    monkeypatch.setattr(app_context, "get_server", throw_err)

    with pytest.raises(Exception):
        (
            await get_bedrock_process_info(
                request=GetBedrockProcessInfoRequest(server_name="test_server"),
                app_context=app_context,
            )
        ).model_dump(mode="python")
