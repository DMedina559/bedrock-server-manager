import pytest


def test_manage_json_config(real_bedrock_server):
    """Test getting, setting, and checking values via _manage_json_config."""
    server = real_bedrock_server

    # Since it uses the DB in the background, we can just use setters and getters
    server._manage_json_config(
        key="server_info.status", operation="write", value="STOPPED"
    )
    server._manage_json_config(
        key="custom.test_key", operation="write", value="test_value"
    )

    assert (
        server._manage_json_config(key="server_info.status", operation="read")
        == "STOPPED"
    )
    assert (
        server._manage_json_config(key="custom.test_key", operation="read")
        == "test_value"
    )

    server._manage_json_config(
        key="custom.test_key", operation="write", value="new_value"
    )
    assert (
        server._manage_json_config(key="custom.test_key", operation="read")
        == "new_value"
    )

    # Check boolean values correctly read
    server._manage_json_config(key="custom.bool_val", operation="write", value=True)
    assert server._manage_json_config(key="custom.bool_val", operation="read") is True

    # Check invalid action
    from bedrock_server_manager.error import UserInputError

    with pytest.raises(UserInputError):
        server._manage_json_config(key="key", operation="invalid_action")


def test_get_set_version(real_bedrock_server):
    """Test standard getters and setters for version."""
    server = real_bedrock_server
    server.set_version("1.20.10.01")
    assert server.get_version() == "1.20.10.01"


def test_get_set_status_in_config(real_bedrock_server):
    """Test standard getters and setters for status."""
    server = real_bedrock_server
    server.set_status_in_config("RUNNING")
    assert server.get_status_from_config() == "RUNNING"


def test_get_set_autoupdate(real_bedrock_server):
    """Test autoupdate property methods."""
    server = real_bedrock_server
    server.set_autoupdate(True)
    assert server.get_autoupdate() is True


def test_get_set_autostart(real_bedrock_server):
    """Test autostart property methods."""
    server = real_bedrock_server
    server.set_autostart(True)
    assert server.get_autostart() is True


def test_get_set_target_version(real_bedrock_server):
    """Test target version property methods."""
    server = real_bedrock_server
    server.set_target_version("latest")
    assert server.get_target_version() == "latest"
