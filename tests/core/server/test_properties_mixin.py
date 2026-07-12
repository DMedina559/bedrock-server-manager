import pytest


def test_get_server_properties(real_bedrock_server):
    """Test retrieving server properties from file."""
    server = real_bedrock_server
    with open(server.server_properties_path, "w") as f:
        f.write("key1=value1\n")
        f.write("key2=value2\n")

    properties = server.get_server_properties()
    assert properties == {"key1": "value1", "key2": "value2"}


def test_get_server_properties_malformed_line(real_bedrock_server):
    """Test retrieving server properties ignores malformed lines."""
    server = real_bedrock_server
    with open(server.server_properties_path, "w") as f:
        f.write("key1=value1\n")
        f.write("malformed\n")
        f.write("key2=value2\n")

    properties = server.get_server_properties()
    assert properties == {"key1": "value1", "key2": "value2"}


def test_get_server_properties_missing_file(real_bedrock_server):
    """Test getting properties when file is missing raises error."""
    server = real_bedrock_server
    import os

    from bedrock_server_manager.error import AppFileNotFoundError

    if os.path.exists(server.server_properties_path):
        os.remove(server.server_properties_path)

    with pytest.raises(AppFileNotFoundError):
        server.get_server_properties()


def test_get_server_property(real_bedrock_server):
    """Test retrieving a single property."""
    server = real_bedrock_server
    with open(server.server_properties_path, "w") as f:
        f.write("key1=value1\n")

    assert server.get_server_property("key1") == "value1"
    assert server.get_server_property("non_existent") is None


def test_set_server_property(real_bedrock_server):
    """Test setting a new or existing property."""
    server = real_bedrock_server
    with open(server.server_properties_path, "w") as f:
        f.write("key1=value1\n")

    server.set_server_property("key2", "value2")
    server.set_server_property("key1", "updated_value")

    with open(server.server_properties_path, "r") as f:
        lines = f.readlines()
        assert "key1=updated_value\n" in lines
        assert "key2=value2\n" in lines
