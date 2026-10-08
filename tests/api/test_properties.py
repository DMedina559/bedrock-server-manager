from pathlib import Path

import pytest

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


async def test_property_api_updates_real_server_configuration(
    app_context, real_bedrock_server
):
    name = real_bedrock_server.server_name
    result = await set_properties(
        SetPropertiesRequest(
            server_name=name,
            properties_to_update={"server-name": "API Server", "max-players": "30"},
        ),
        app_context=app_context,
    )
    assert result.status == "success"
    properties = await get_properties(
        GetPropertiesRequest(server_name=name), app_context=app_context
    )
    assert properties.properties["server-name"] == "API Server"
    assert "server-name=API Server" in properties.raw_content


async def test_property_api_validates_before_writing(app_context, real_bedrock_server):
    path = Path(real_bedrock_server.server_dir) / "server.properties"
    original = path.read_bytes()
    with pytest.raises(UserInputError):
        await set_properties(
            SetPropertiesRequest(
                server_name=real_bedrock_server.server_name,
                properties_to_update={"server-port": "0"},
            ),
            app_context=app_context,
        )
    assert path.read_bytes() == original


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
