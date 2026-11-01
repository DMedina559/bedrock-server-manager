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


async def test_property_api_updates_and_validates_before_writing(
    app_context, real_bedrock_server
):
    name = real_bedrock_server.server_name
    path = Path(real_bedrock_server.paths.server_dir) / "server.properties"
    original = path.read_bytes()

    with pytest.raises(UserInputError):
        await set_properties(
            SetPropertiesRequest(
                server_name=name,
                properties_to_update={"server-port": "0"},
            ),
            app_context=app_context,
        )
    assert path.read_bytes() == original

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


def test_validate_property_value_and_non_finite_numbers():
    """Test validate_property_value limits string, integer, and non-finite float validation."""
    for prop, val in (("server-port", "19132"), ("server-name", "Hello")):
        assert (
            validate_property_value(
                request=ValidatePropertyValueRequest(property_name=prop, value=val)
            ).status
            == "success"
        )

    for prop, val in (
        ("server-name", "Bad;Name"),
        ("level-name", "Bad@Name"),
        ("server-name", "A" * 101),
        ("level-name", "B" * 81),
        ("server-port", "0"),
        ("server-port", "65536"),
        ("server-portv6", "0"),
        ("server-portv6", "90000"),
        ("max-players", "0"),
        ("view-distance", "4"),
        ("tick-distance", "15"),
        ("tick-distance", "3"),
    ):
        assert (
            validate_property_value(
                request=ValidatePropertyValueRequest(property_name=prop, value=val)
            ).valid
            is False
        )

    for name in (
        "player-position-acceptance-threshold",
        "server-authoritative-block-breaking-pick-range-scalar",
        "player-movement-action-direction-threshold",
    ):
        for value in ("nan", "inf", "-inf", "NaN"):
            assert not validate_property_value(
                ValidatePropertyValueRequest(property_name=name, value=value)
            ).valid
