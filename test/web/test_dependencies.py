import pytest
from unittest.mock import patch, MagicMock
from bedrock_server_manager.web.dependencies import validate_server_exists
from fastapi import HTTPException
from bedrock_server_manager.error import InvalidServerNameError

# Test data
TEST_SERVER_NAME = "test-server"


@pytest.mark.asyncio
async def test_validate_server_exists(app_context, real_bedrock_server):
    """Test that a valid server passes validation."""
    request = MagicMock()
    request.app.state.app_context = app_context
    result = await validate_server_exists(request, real_bedrock_server.server_name)
    assert result == real_bedrock_server.server_name


@pytest.mark.asyncio
async def test_validate_server_not_found(app_context):
    """Test that a non-existent server raises an HTTPException."""
    request = MagicMock()
    request.app.state.app_context = app_context
    with pytest.raises(HTTPException) as excinfo:
        await validate_server_exists(request, "non-existent-server")
    assert excinfo.value.status_code == 404
    assert "is not installed or the installation is invalid" in excinfo.value.detail


@pytest.mark.asyncio
async def test_validate_server_invalid_name(app_context):
    """Test that an invalid server name raises an HTTPException."""
    request = MagicMock()
    request.app.state.app_context = app_context
    with pytest.raises(HTTPException) as excinfo:
        await validate_server_exists(request, "invalid name")
    assert excinfo.value.status_code == 400
    assert "Invalid server name format" in excinfo.value.detail
