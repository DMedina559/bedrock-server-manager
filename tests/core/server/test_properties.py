import os

import pytest

from bedrock_server_manager.error import AppFileNotFoundError


async def test_server_properties_operations(real_bedrock_server):
    """Test getting, setting, malformed line handling, and missing file for server.properties."""
    server = real_bedrock_server

    with open(server.paths.server_properties_path, "w") as f:
        f.write("key1=value1\nmalformed\nkey2=value2\n")

    properties = await server.properties.get_server_properties()
    assert properties == {"key1": "value1", "key2": "value2"}
    assert await server.properties.get_server_property("key1") == "value1"
    assert await server.properties.get_server_property("non_existent") is None

    await server.properties.set_server_property("key3", "value3")
    await server.properties.set_server_property("key1", "updated_value")

    with open(server.paths.server_properties_path, "r") as f:
        lines = f.readlines()
        assert "key1=updated_value\n" in lines
        assert "key3=value3\n" in lines

    os.remove(server.paths.server_properties_path)
    with pytest.raises(AppFileNotFoundError):
        await server.properties.get_server_properties()
