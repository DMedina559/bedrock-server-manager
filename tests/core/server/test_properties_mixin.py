def test_get_server_properties(real_bedrock_server):
    server = real_bedrock_server
    with open(server.server_properties_path, "w") as f:
        f.write("key1=value1\n")
        f.write("key2=value2\n")

    properties = server.get_server_properties()
    assert properties == {"key1": "value1", "key2": "value2"}


def test_get_server_properties_malformed_line(real_bedrock_server):
    server = real_bedrock_server
    with open(server.server_properties_path, "w") as f:
        f.write("key1=value1\n")
        f.write("malformed\n")
        f.write("key2=value2\n")

    properties = server.get_server_properties()
    assert properties == {"key1": "value1", "key2": "value2"}


def test_set_server_property(real_bedrock_server):
    server = real_bedrock_server
    with open(server.server_properties_path, "w") as f:
        f.write("key1=value1\n")

    server.set_server_property("key2", "value2")

    with open(server.server_properties_path, "r") as f:
        lines = f.readlines()
        assert "key1=value1\n" in lines
        assert "key2=value2\n" in lines
