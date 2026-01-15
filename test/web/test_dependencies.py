from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from bedrock_server_manager.error import InvalidServerNameError
from bedrock_server_manager.web.dependencies import validate_server_exists

# Test data
TEST_SERVER_NAME = "test-server"


@pytest.mark.asyncio
async def test_validate_server_exists(app_context, real_bedrock_server):
    """Test that a valid server passes validation."""
    result = await validate_server_exists(real_bedrock_server.server_name, app_context)
    assert result == real_bedrock_server.server_name


@pytest.mark.asyncio
async def test_validate_server_not_found(app_context):
    """Test that a non-existent server raises an HTTPException."""
    with pytest.raises(HTTPException) as excinfo:
        await validate_server_exists("non-existent-server", app_context)
    assert excinfo.value.status_code == 404
    assert "is not installed or the installation is invalid" in excinfo.value.detail


@pytest.mark.asyncio
async def test_validate_server_invalid_name(app_context):
    """Test that an invalid server name raises an HTTPException."""
    with pytest.raises(HTTPException) as excinfo:
        await validate_server_exists("invalid name", app_context)
    assert excinfo.value.status_code == 400
    assert "Invalid server name format" in excinfo.value.detail
