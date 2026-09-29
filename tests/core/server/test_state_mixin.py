import pytest

from bedrock_server_manager.error import UserInputError


async def test_manage_json_config(real_bedrock_server):
    """Test getting, setting, and checking values via _manage_json_config."""
    server = real_bedrock_server

    # Since it uses the DB in the background, we can just use setters and getters
    await server._manage_json_config(
        key="server_info.status", operation="write", value="STOPPED"
    )
    await server._manage_json_config(
        key="custom.test_key", operation="write", value="test_value"
    )

    assert (
        await server._manage_json_config(key="server_info.status", operation="read")
        == "STOPPED"
    )
    assert (
        await server._manage_json_config(key="custom.test_key", operation="read")
        == "test_value"
    )

    await server._manage_json_config(
        key="custom.test_key", operation="write", value="new_value"
    )
    assert (
        await server._manage_json_config(key="custom.test_key", operation="read")
        == "new_value"
    )

    # Check boolean values correctly read
    await server._manage_json_config(
        key="custom.bool_val", operation="write", value=True
    )
    assert (
        await server._manage_json_config(key="custom.bool_val", operation="read")
        is True
    )

    # Check invalid action
    with pytest.raises(UserInputError):
        await server._manage_json_config(key="key", operation="invalid_action")


async def test_get_set_version(real_bedrock_server):
    """Test standard getters and setters for version."""
    server = real_bedrock_server
    await server.set_version("1.20.10.01")
    assert await server.get_version() == "1.20.10.01"


async def test_get_set_status_in_config(real_bedrock_server):
    """Test standard getters and setters for status."""
    server = real_bedrock_server
    await server.set_status_in_config("RUNNING")
    assert await server.get_status_from_config() == "RUNNING"


async def test_get_set_autoupdate(real_bedrock_server):
    """Test autoupdate property methods."""
    server = real_bedrock_server
    await server.set_autoupdate(True)
    assert await server.get_autoupdate() is True


async def test_get_set_autostart(real_bedrock_server):
    """Test autostart property methods."""
    server = real_bedrock_server
    await server.set_autostart(True)
    assert await server.get_autostart() is True


async def test_get_set_target_version(real_bedrock_server):
    """Test target version property methods."""
    server = real_bedrock_server
    await server.set_target_version("latest")
    assert await server.get_target_version() == "latest"
