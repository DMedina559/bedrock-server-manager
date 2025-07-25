import pytest
import os
import json
import tempfile
import shutil
from bedrock_server_manager.core.server.config_management_mixin import (
    ServerConfigManagementMixin,
)
from bedrock_server_manager.core.server.base_server_mixin import BedrockServerBaseMixin
from bedrock_server_manager.config.settings import Settings


class SetupBedrockServer(ServerConfigManagementMixin, BedrockServerBaseMixin):
    pass


@pytest.fixture
def config_management_fixture():
    temp_dir = tempfile.mkdtemp()
    server_name = "test_server"
    settings = Settings()
    settings.set("paths.servers", os.path.join(temp_dir, "servers"))
    settings._config_dir_path = os.path.join(temp_dir, "config")

    server = SetupBedrockServer(server_name=server_name, settings_instance=settings)
    os.makedirs(server.server_dir, exist_ok=True)

    # Create a default server.properties file for the tests
    properties_path = server.server_properties_path
    with open(properties_path, "w") as f:
        f.write("key1=value1\n")

    yield server

    shutil.rmtree(temp_dir)


def test_get_server_properties(config_management_fixture):
    server = config_management_fixture
    properties_path = server.server_properties_path
    with open(properties_path, "w") as f:
        f.write("key1=value1\n")
        f.write("key2=value2\n")

    properties = server.get_server_properties()
    assert properties == {"key1": "value1", "key2": "value2"}


def test_get_server_properties_empty_file(config_management_fixture):
    server = config_management_fixture
    properties_path = server.server_properties_path
    with open(properties_path, "w") as f:
        f.write("")

    properties = server.get_server_properties()
    assert properties == {}


def test_get_server_properties_malformed_line(config_management_fixture):
    server = config_management_fixture
    properties_path = server.server_properties_path
    with open(properties_path, "w") as f:
        f.write("key1=value1\n")
        f.write("malformed\n")
        f.write("key2=value2\n")

    properties = server.get_server_properties()
    assert properties == {"key1": "value1", "key2": "value2"}


def test_get_server_property_missing_file(config_management_fixture):
    server = config_management_fixture
    os.remove(server.server_properties_path)
    assert server.get_server_property("key1", "default") == "default"


def test_set_server_property(config_management_fixture):
    server = config_management_fixture
    properties_path = server.server_properties_path
    with open(properties_path, "w") as f:
        f.write("key1=value1\n")

    server.set_server_property("key2", "value2")

    with open(properties_path, "r") as f:
        lines = f.readlines()
        assert "key1=value1\n" in lines
        assert "key2=value2\n" in lines


def test_get_allowlist(config_management_fixture):
    server = config_management_fixture
    allowlist_path = server.allowlist_json_path
    allowlist_data = [{"name": "player1", "xuid": "12345", "ignoresPlayerLimit": False}]
    with open(allowlist_path, "w") as f:
        json.dump(allowlist_data, f)

    allowlist = server.get_allowlist()
    assert allowlist == allowlist_data


def test_add_to_allowlist(config_management_fixture):
    server = config_management_fixture
    allowlist_data = [{"name": "player1", "xuid": "12345"}]
    server.add_to_allowlist(allowlist_data)

    allowlist_path = server.allowlist_json_path
    with open(allowlist_path, "r") as f:
        data = json.load(f)
        assert data == [
            {"name": "player1", "xuid": "12345", "ignoresPlayerLimit": False}
        ]


def test_get_allowlist_missing_file(config_management_fixture):
    server = config_management_fixture
    allowlist = server.get_allowlist()
    assert allowlist == []


def test_get_allowlist_empty_file(config_management_fixture):
    server = config_management_fixture
    allowlist_path = server.allowlist_json_path
    with open(allowlist_path, "w") as f:
        f.write("")

    allowlist = server.get_allowlist()
    assert allowlist == []


def test_get_allowlist_invalid_json(config_management_fixture):
    server = config_management_fixture
    allowlist_path = server.allowlist_json_path
    with open(allowlist_path, "w") as f:
        f.write("{invalid_json}")

    with pytest.raises(Exception):
        server.get_allowlist()


def test_get_allowlist_json_object(config_management_fixture):
    server = config_management_fixture
    allowlist_path = server.allowlist_json_path
    with open(allowlist_path, "w") as f:
        json.dump({"key": "value"}, f)

    allowlist = server.get_allowlist()
    assert allowlist == []


def test_get_allowlist_missing_server_dir(config_management_fixture):
    server = config_management_fixture
    shutil.rmtree(server.server_dir)
    with pytest.raises(Exception):
        server.get_allowlist()


def test_add_to_allowlist_non_existent_file(config_management_fixture):
    server = config_management_fixture
    players_to_add = [{"name": "player2", "xuid": "67890"}]
    server.add_to_allowlist(players_to_add)
    allowlist = server.get_allowlist()
    assert any(p["name"] == "player2" for p in allowlist)


def test_add_to_allowlist_player_already_exists(config_management_fixture):
    server = config_management_fixture
    players_to_add = [{"name": "player1", "xuid": "12345"}]
    server.add_to_allowlist(players_to_add)
    result = server.add_to_allowlist(players_to_add)
    assert result == 0


def test_add_to_allowlist_invalid_entry(config_management_fixture):
    server = config_management_fixture
    players_to_add = ["invalid_entry"]
    server.add_to_allowlist(players_to_add)
    allowlist = server.get_allowlist()
    assert len(allowlist) == 0


def test_add_to_allowlist_missing_name(config_management_fixture):
    server = config_management_fixture
    players_to_add = [{"xuid": "12345"}]
    server.add_to_allowlist(players_to_add)
    allowlist = server.get_allowlist()
    assert len(allowlist) == 0


def test_add_to_allowlist_multiple_players(config_management_fixture):
    server = config_management_fixture
    players_to_add = [
        {"name": "player2", "xuid": "67890"},
        {"name": "player3", "xuid": "54321"},
        {"name": "player2", "xuid": "09876"},
    ]
    server.add_to_allowlist(players_to_add)
    allowlist = server.get_allowlist()
    assert len(allowlist) == 2
    assert any(p["name"] == "player2" for p in allowlist)
    assert any(p["name"] == "player3" for p in allowlist)


def test_add_to_allowlist_unwritable_file(config_management_fixture):
    server = config_management_fixture
    allowlist_path = server.allowlist_json_path
    with open(allowlist_path, "w") as f:
        f.write("[]")
    os.chmod(allowlist_path, 0o444)  # Read-only
    players_to_add = [{"name": "player2", "xuid": "67890"}]
    with pytest.raises(Exception):
        server.add_to_allowlist(players_to_add)
    os.chmod(allowlist_path, 0o644)


def test_remove_from_allowlist_player_not_found(config_management_fixture):
    server = config_management_fixture
    result = server.remove_from_allowlist("non_existent_player")
    assert result is False


def test_remove_from_allowlist_empty_file(config_management_fixture):
    server = config_management_fixture
    result = server.remove_from_allowlist("player1")
    assert result is False


def test_remove_from_allowlist_unwritable_file(config_management_fixture):
    server = config_management_fixture
    players_to_add = [{"name": "player1", "xuid": "12345"}]
    server.add_to_allowlist(players_to_add)
    allowlist_path = server.allowlist_json_path
    os.chmod(allowlist_path, 0o444)  # Read-only
    with pytest.raises(Exception):
        server.remove_from_allowlist("player1")
    os.chmod(allowlist_path, 0o644)


def test_set_player_permission_new_player(config_management_fixture):
    server = config_management_fixture
    server.set_player_permission("67890", "operator", "player2")
    permissions = server.get_formatted_permissions({"67890": "player2"})
    assert any(
        p["xuid"] == "67890" and p["permission_level"] == "operator"
        for p in permissions
    )


def test_set_player_permission_update_existing(config_management_fixture):
    server = config_management_fixture
    server.set_player_permission("12345", "member", "player1")
    server.set_player_permission("12345", "operator", "player1_updated")
    permissions = server.get_formatted_permissions({"12345": "player1_updated"})
    assert any(
        p["xuid"] == "12345" and p["permission_level"] == "operator"
        for p in permissions
    )
    assert any(p["name"] == "player1_updated" for p in permissions)


def test_set_player_permission_invalid_level(config_management_fixture):
    server = config_management_fixture
    with pytest.raises(Exception):
        server.set_player_permission("12345", "invalid_level")


def test_set_player_permission_empty_xuid(config_management_fixture):
    server = config_management_fixture
    with pytest.raises(Exception):
        server.set_player_permission("", "operator")


def test_set_player_permission_empty_level(config_management_fixture):
    server = config_management_fixture
    with pytest.raises(Exception):
        server.set_player_permission("12345", "")


def test_set_player_permission_non_existent_file(config_management_fixture):
    server = config_management_fixture
    server.set_player_permission("67890", "operator", "player2")
    permissions = server.get_formatted_permissions({"67890": "player2"})
    assert any(
        p["xuid"] == "67890" and p["permission_level"] == "operator"
        for p in permissions
    )


def test_set_player_permission_unwritable_file(config_management_fixture):
    server = config_management_fixture
    permissions_path = server.permissions_json_path
    with open(permissions_path, "w") as f:
        f.write("[]")
    os.chmod(permissions_path, 0o444)  # Read-only
    with pytest.raises(Exception):
        server.set_player_permission("12345", "operator", "player1")
    os.chmod(permissions_path, 0o644)


def test_get_formatted_permissions_missing_file(config_management_fixture):
    server = config_management_fixture
    with pytest.raises(Exception):
        server.get_formatted_permissions({})


def test_get_formatted_permissions_empty_file(config_management_fixture):
    server = config_management_fixture
    permissions_path = server.permissions_json_path
    with open(permissions_path, "w") as f:
        f.write("[]")
    permissions = server.get_formatted_permissions({})
    assert permissions == []


def test_get_formatted_permissions_malformed_entries(config_management_fixture):
    server = config_management_fixture
    permissions_path = server.permissions_json_path
    with open(permissions_path, "w") as f:
        f.write('[{"xuid": "12345"}, {"permission": "operator"}]')
    permissions = server.get_formatted_permissions({})
    assert len(permissions) == 0


def test_get_formatted_permissions_xuid_not_in_map(config_management_fixture):
    server = config_management_fixture
    permissions_path = server.permissions_json_path
    permissions_data = [{"permission": "operator", "xuid": "12345"}]
    with open(permissions_path, "w") as f:
        json.dump(permissions_data, f)
    permissions = server.get_formatted_permissions({})
    assert any(p["xuid"] == "12345" and "Unknown" in p["name"] for p in permissions)


def test_get_formatted_permissions(config_management_fixture):
    server = config_management_fixture
    permissions_path = server.permissions_json_path
    permissions_data = [{"permission": "operator", "xuid": "12345"}]
    with open(permissions_path, "w") as f:
        json.dump(permissions_data, f)

    permissions = server.get_formatted_permissions({"12345": "player1"})
    assert permissions == [
        {"xuid": "12345", "name": "player1", "permission_level": "operator"}
    ]


def test_set_player_permission(config_management_fixture):
    server = config_management_fixture
    server.set_player_permission("12345", "operator", "player1")

    permissions_path = server.permissions_json_path
    with open(permissions_path, "r") as f:
        data = json.load(f)
        assert data == [{"permission": "operator", "xuid": "12345", "name": "player1"}]


def test_set_server_property_new_property(config_management_fixture):
    server = config_management_fixture
    server.set_server_property("new_key", "new_value")
    properties = server.get_server_properties()
    assert properties["new_key"] == "new_value"


def test_set_server_property_update_property(config_management_fixture):
    server = config_management_fixture
    server.set_server_property("key1", "new_value")
    properties = server.get_server_properties()
    assert properties["key1"] == "new_value"


def test_set_server_property_invalid_value(config_management_fixture):
    server = config_management_fixture
    with pytest.raises(Exception):
        server.set_server_property("key1", "\x00")


def test_set_server_property_missing_file(config_management_fixture):
    server = config_management_fixture
    properties_path = server.server_properties_path
    with open(properties_path, "w") as f:
        f.write("key1=value1\n")
    os.remove(properties_path)
    with pytest.raises(Exception):
        server.set_server_property("key1", "value1")


def test_set_server_property_unwritable_file(config_management_fixture):
    server = config_management_fixture
    properties_path = server.server_properties_path
    with open(properties_path, "w") as f:
        f.write("key1=value1\n")
    os.chmod(properties_path, 0o444)  # Read-only
    with pytest.raises(Exception):
        server.set_server_property("key1", "new_value")
    os.chmod(properties_path, 0o644)


def test_get_server_properties_missing_file(config_management_fixture):
    server = config_management_fixture
    properties_path = server.server_properties_path
    os.remove(properties_path)
    with pytest.raises(Exception):
        server.get_server_properties()


def test_get_server_properties_empty_file(config_management_fixture):
    server = config_management_fixture
    properties_path = server.server_properties_path
    with open(properties_path, "w") as f:
        f.write("")
    properties = server.get_server_properties()
    assert properties == {}


def test_get_server_properties_malformed_lines(config_management_fixture):
    server = config_management_fixture
    properties_path = server.server_properties_path
    with open(properties_path, "w") as f:
        f.write("key1=value1\n")
        f.write("malformed_line\n")
        f.write("key2=value2\n")
    properties = server.get_server_properties()
    assert properties == {"key1": "value1", "key2": "value2"}


def test_get_server_property_existing(config_management_fixture):
    server = config_management_fixture
    value = server.get_server_property("key1")
    assert value == "value1"


def test_get_server_property_non_existent_with_default(config_management_fixture):
    server = config_management_fixture
    value = server.get_server_property("non_existent_key", default="default_value")
    assert value == "default_value"


def test_get_server_property_missing_file(config_management_fixture):
    server = config_management_fixture
    properties_path = server.server_properties_path
    os.remove(properties_path)
    value = server.get_server_property("key1", default="default_value")
    assert value == "default_value"
