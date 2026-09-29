from unittest.mock import AsyncMock, MagicMock

import pytest

from bedrock_server_manager.api.properties import (
    get_properties,
    set_properties,
    validate_property_value,
)
from bedrock_server_manager.error import InvalidServerNameError


async def test_get_properties_success(app_context, monkeypatch):
    """Test get_properties maps accurately to BedrockServer properties output."""
    mock_server = MagicMock()
    mock_server.get_server_properties = AsyncMock(
        return_value={"server-name": "mc server"}
    )
    mock_server.server_properties_path = "test/path"
    monkeypatch.setattr(app_context, "get_server", lambda x: mock_server)

    # Mock aiofiles for properties read
    import unittest.mock

    mock_file = AsyncMock()
    mock_file.read.return_value = "raw data"

    mock_file.__aenter__.return_value = mock_file

    with unittest.mock.patch("aiofiles.open", return_value=mock_file):
        result = await get_properties("test_server", app_context)

    assert result["status"] == "success"
    assert result["properties"]["server-name"] == "mc server"
    assert result["raw_content"] == "raw data"


async def test_get_properties_missing_name(app_context):
    """Test get_properties catches empty server names smoothly without raising."""
    result = await get_properties("", app_context)

    assert result["status"] == "error"
    assert "cannot be empty" in result["message"]


def test_validate_property_value():
    """Test validate_property_value limits string validation properly across specific config keys."""
    # Test valid
    assert validate_property_value("server-port", "19132")["status"] == "success"
    assert validate_property_value("server-name", "Hello")["status"] == "success"

    # Test invalid string constraints
    assert validate_property_value("server-name", "Bad;Name")["status"] == "error"
    assert validate_property_value("level-name", "Bad@Name")["status"] == "error"
    assert validate_property_value("server-name", "A" * 101)["status"] == "error"
    assert validate_property_value("level-name", "B" * 81)["status"] == "error"

    # Test numerical constraints
    assert validate_property_value("server-port", "0")["status"] == "error"
    assert validate_property_value("server-port", "65536")["status"] == "error"
    assert validate_property_value("server-portv6", "0")["status"] == "error"
    assert validate_property_value("server-portv6", "90000")["status"] == "error"
    assert validate_property_value("max-players", "0")["status"] == "error"
    assert validate_property_value("view-distance", "4")["status"] == "error"
    assert validate_property_value("tick-distance", "15")["status"] == "error"
    assert validate_property_value("tick-distance", "3")["status"] == "error"


async def test_set_properties_success(app_context, monkeypatch):
    """Test set_properties maps properly calling BedrockServer validation and set operations."""
    mock_server = MagicMock()
    mock_server.set_server_property = AsyncMock()
    monkeypatch.setattr(app_context, "get_server", lambda x: mock_server)

    # Bypassing the stop_before lock via monkeypatching context manager
    monkeypatch.setattr(
        "bedrock_server_manager.api.properties.server_lifecycle_manager", MagicMock()
    )

    result = await set_properties(
        "test_server", {"server-port": "19132", "server-name": "mc"}, app_context
    )

    assert result["status"] == "success"
    assert mock_server.set_server_property.call_count == 2
    mock_server.set_server_property.assert_any_call("server-name", "mc")


async def test_set_properties_validation_failure(app_context):
    """Test set_properties returns a validation error gracefully preventing writes."""
    result = await set_properties("test_server", {"server-port": "0"}, app_context)

    assert result["status"] == "error"
    assert "Validation failed" in result["message"]


async def test_set_properties_empty_name(app_context):
    """Test set_properties validates server names rigidly before proceeding."""
    with pytest.raises(InvalidServerNameError):
        await set_properties("", {"server-name": "mc"}, app_context)


async def test_set_properties_type_error(app_context):
    """Test set_properties validates payload typing directly."""
    with pytest.raises(TypeError):
        await set_properties("test_server", "not_a_dict", app_context)
