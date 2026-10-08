from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from bedrock_server_manager.api.models import (
    GetPropertiesRequest,
    SetPropertiesRequest,
    ValidatePropertyValueRequest,
)
from bedrock_server_manager.api.properties import (
    get_properties,
    set_properties,
    validate_property_value,
)
from bedrock_server_manager.error import UserInputError


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
        result = (
            await get_properties(
                request=GetPropertiesRequest(server_name="test_server"),
                app_context=app_context,
            )
        ).model_dump(mode="python")

    assert result["status"] == "success"
    assert result["properties"]["server-name"] == "mc server"
    assert result["raw_content"] == "raw data"


async def test_get_properties_missing_name(app_context):
    """Test get_properties catches empty server names smoothly without raising."""
    with pytest.raises(ValidationError):
        (
            await get_properties(
                request=GetPropertiesRequest(server_name=""), app_context=app_context
            )
        ).model_dump(mode="python")


def test_validate_property_value():
    """Test validate_property_value limits string validation properly across specific config keys."""
    # Test valid
    assert (
        validate_property_value(
            request=ValidatePropertyValueRequest(
                property_name="server-port", value="19132"
            )
        ).model_dump(mode="python")["status"]
        == "success"
    )
    assert (
        validate_property_value(
            request=ValidatePropertyValueRequest(
                property_name="server-name", value="Hello"
            )
        ).model_dump(mode="python")["status"]
        == "success"
    )

    # Test invalid string constraints
    assert (
        validate_property_value(
            request=ValidatePropertyValueRequest(
                property_name="server-name", value="Bad;Name"
            )
        ).model_dump(mode="python")["valid"]
        is False
    )
    assert (
        validate_property_value(
            request=ValidatePropertyValueRequest(
                property_name="level-name", value="Bad@Name"
            )
        ).model_dump(mode="python")["valid"]
        is False
    )
    assert (
        validate_property_value(
            request=ValidatePropertyValueRequest(
                property_name="server-name", value="A" * 101
            )
        ).model_dump(mode="python")["valid"]
        is False
    )
    assert (
        validate_property_value(
            request=ValidatePropertyValueRequest(
                property_name="level-name", value="B" * 81
            )
        ).model_dump(mode="python")["valid"]
        is False
    )

    # Test numerical constraints
    assert (
        validate_property_value(
            request=ValidatePropertyValueRequest(property_name="server-port", value="0")
        ).model_dump(mode="python")["valid"]
        is False
    )
    assert (
        validate_property_value(
            request=ValidatePropertyValueRequest(
                property_name="server-port", value="65536"
            )
        ).model_dump(mode="python")["valid"]
        is False
    )
    assert (
        validate_property_value(
            request=ValidatePropertyValueRequest(
                property_name="server-portv6", value="0"
            )
        ).model_dump(mode="python")["valid"]
        is False
    )
    assert (
        validate_property_value(
            request=ValidatePropertyValueRequest(
                property_name="server-portv6", value="90000"
            )
        ).model_dump(mode="python")["valid"]
        is False
    )
    assert (
        validate_property_value(
            request=ValidatePropertyValueRequest(property_name="max-players", value="0")
        ).model_dump(mode="python")["valid"]
        is False
    )
    assert (
        validate_property_value(
            request=ValidatePropertyValueRequest(
                property_name="view-distance", value="4"
            )
        ).model_dump(mode="python")["valid"]
        is False
    )
    assert (
        validate_property_value(
            request=ValidatePropertyValueRequest(
                property_name="tick-distance", value="15"
            )
        ).model_dump(mode="python")["valid"]
        is False
    )
    assert (
        validate_property_value(
            request=ValidatePropertyValueRequest(
                property_name="tick-distance", value="3"
            )
        ).model_dump(mode="python")["valid"]
        is False
    )


async def test_set_properties_success(app_context, monkeypatch):
    """Test set_properties maps properly calling BedrockServer validation and set operations."""
    mock_server = MagicMock()
    mock_server.set_server_property = AsyncMock()
    monkeypatch.setattr(app_context, "get_server", lambda x: mock_server)

    # Bypassing the stop_before lock via monkeypatching context manager
    monkeypatch.setattr(
        "bedrock_server_manager.api.properties.server_lifecycle_manager", MagicMock()
    )

    result = (
        await set_properties(
            request=SetPropertiesRequest(
                server_name="test_server",
                properties_to_update={"server-port": "19132", "server-name": "mc"},
            ),
            app_context=app_context,
        )
    ).model_dump(mode="python")

    assert result["status"] == "success"
    assert mock_server.set_server_property.call_count == 2
    mock_server.set_server_property.assert_any_call("server-name", "mc")


async def test_set_properties_validation_failure(app_context):
    """Test set_properties returns a validation error gracefully preventing writes."""
    with pytest.raises(UserInputError):
        (
            await set_properties(
                request=SetPropertiesRequest(
                    server_name="test_server", properties_to_update={"server-port": "0"}
                ),
                app_context=app_context,
            )
        ).model_dump(mode="python")


async def test_set_properties_empty_name(app_context):
    """Test set_properties validates server names rigidly before proceeding."""
    with pytest.raises(ValidationError):
        (
            await set_properties(
                request=SetPropertiesRequest(
                    server_name="", properties_to_update={"server-name": "mc"}
                ),
                app_context=app_context,
            )
        ).model_dump(mode="python")


async def test_set_properties_type_error(app_context):
    """Test set_properties validates payload typing directly."""
    with pytest.raises(ValidationError):
        (
            await set_properties(
                request=SetPropertiesRequest(
                    server_name="test_server", properties_to_update="not_a_dict"
                ),
                app_context=app_context,
            )
        ).model_dump(mode="python")


@pytest.mark.parametrize(
    "name",
    [
        "player-position-acceptance-threshold",
        "server-authoritative-block-breaking-pick-range-scalar",
        "player-movement-action-direction-threshold",
    ],
)
@pytest.mark.parametrize("value", ["nan", "inf", "-inf", "NaN"])
def test_numeric_properties_reject_non_finite_numbers(name, value):
    from bedrock_server_manager.api.models import ValidatePropertyValueRequest
    from bedrock_server_manager.api.properties import validate_property_value

    result = validate_property_value(
        ValidatePropertyValueRequest(property_name=name, value=value)
    )
    assert not result.valid
