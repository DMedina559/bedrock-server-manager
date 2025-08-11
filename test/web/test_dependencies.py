import pytest
from unittest.mock import patch, MagicMock
from bedrock_server_manager.web.dependencies import validate_server_exists
from fastapi import HTTPException
from bedrock_server_manager.error import InvalidServerNameError

# Test data
TEST_SERVER_NAME = "test-server"


@pytest.mark.asyncio
@patch("bedrock_server_manager.api.utils.validate_server_exist")
async def test_validate_server_exists(mock_validate):
    """Test that a valid server passes validation."""
    mock_validate.return_value = {"status": "success"}
    request = MagicMock()
    app_context = MagicMock()
    request.app.state.app_context = app_context
    result = await validate_server_exists(request, TEST_SERVER_NAME)
    assert result == TEST_SERVER_NAME
    mock_validate.assert_called_once_with(
        server_name=TEST_SERVER_NAME, app_context=app_context
    )


@pytest.mark.asyncio
@patch("bedrock_server_manager.api.utils.validate_server_exist")
async def test_validate_server_not_found(mock_validate):
    """Test that a non-existent server raises an HTTPException."""
    mock_validate.return_value = {"status": "error", "message": "Server not found"}
    request = MagicMock()
    app_context = MagicMock()
    request.app.state.app_context = app_context
    with pytest.raises(HTTPException) as excinfo:
        await validate_server_exists(request, TEST_SERVER_NAME)
    assert excinfo.value.status_code == 404
    assert "Server not found" in excinfo.value.detail


@pytest.mark.asyncio
@patch("bedrock_server_manager.api.utils.validate_server_exist")
async def test_validate_server_invalid_name(mock_validate):
    """Test that an invalid server name raises an HTTPException."""
    mock_validate.side_effect = InvalidServerNameError("Invalid server name")
    request = MagicMock()
    app_context = MagicMock()
    request.app.state.app_context = app_context
    with pytest.raises(HTTPException) as excinfo:
        await validate_server_exists(request, TEST_SERVER_NAME)
    assert excinfo.value.status_code == 400
    assert "Invalid server name" in excinfo.value.detail
