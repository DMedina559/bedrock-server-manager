import json
import os

import pytest


def test_set_player_permission_new_player(real_bedrock_server):
    server = real_bedrock_server
    server.set_player_permission("67890", "operator", "player2")
    permissions_path = server.permissions_json_path
    with open(permissions_path, "r") as f:
        permissions_data = json.load(f)
    assert any(
        p["xuid"] == "67890" and p["permission"] == "operator" for p in permissions_data
    )


def test_set_player_permission_update_existing(real_bedrock_server):
    server = real_bedrock_server
    server.set_player_permission("12345", "member", "player1")
    server.set_player_permission("12345", "operator", "player1_updated")
    permissions_path = server.permissions_json_path
    with open(permissions_path, "r") as f:
        permissions_data = json.load(f)
    assert any(
        p["xuid"] == "12345" and p["permission"] == "operator" for p in permissions_data
    )
    assert any(p["name"] == "player1_updated" for p in permissions_data)


def test_set_player_permission_invalid_level(real_bedrock_server):
    server = real_bedrock_server
    with pytest.raises(Exception):
        server.set_player_permission("12345", "invalid_level")


def test_set_player_permission_empty_xuid(real_bedrock_server):
    server = real_bedrock_server
    with pytest.raises(Exception):
        server.set_player_permission("", "operator")


def test_set_player_permission_empty_level(real_bedrock_server):
    server = real_bedrock_server
    with pytest.raises(Exception):
        server.set_player_permission("12345", "")


def test_set_player_permission_non_existent_file(real_bedrock_server):
    server = real_bedrock_server
    server.set_player_permission("67890", "operator", "player2")
    permissions_path = server.permissions_json_path
    with open(permissions_path, "r") as f:
        permissions_data = json.load(f)
    assert any(
        p["xuid"] == "67890" and p["permission"] == "operator" for p in permissions_data
    )


def test_set_player_permission_unwritable_file(real_bedrock_server):
    server = real_bedrock_server
    permissions_path = server.permissions_json_path
    with open(permissions_path, "w") as f:
        f.write("[]")
    os.chmod(permissions_path, 0o444)  # Read-only
    with pytest.raises(Exception):
        server.set_player_permission("12345", "operator", "player1")
    os.chmod(permissions_path, 0o644)


def test_get_formatted_permissions_missing_file(real_bedrock_server):
    server = real_bedrock_server
    with pytest.raises(Exception):
        server.get_formatted_permissions({})


def test_get_formatted_permissions_empty_file(real_bedrock_server):
    server = real_bedrock_server
    permissions_path = server.permissions_json_path
    with open(permissions_path, "w") as f:
        f.write("[]")
    permissions = server.get_formatted_permissions({})
    assert permissions == []


def test_get_formatted_permissions_malformed_entries(real_bedrock_server):
    server = real_bedrock_server
    permissions_path = server.permissions_json_path
    with open(permissions_path, "w") as f:
        f.write('[{"xuid": "12345"}, {"permission": "operator"}]')
    permissions = server.get_formatted_permissions({})
    assert len(permissions) == 0


def test_get_formatted_permissions_xuid_not_in_map(real_bedrock_server):
    server = real_bedrock_server
    permissions_path = server.permissions_json_path
    permissions_data = [{"permission": "operator", "xuid": "12345"}]
    with open(permissions_path, "w") as f:
        json.dump(permissions_data, f)
    permissions = server.get_formatted_permissions({})
    assert any(p["xuid"] == "12345" and "Unknown" in p["name"] for p in permissions)


def test_get_formatted_permissions(real_bedrock_server):
    server = real_bedrock_server
    permissions_path = server.permissions_json_path
    permissions_data = [{"permission": "operator", "xuid": "12345"}]
    with open(permissions_path, "w") as f:
        json.dump(permissions_data, f)

    permissions = server.get_formatted_permissions({"12345": "player1"})
    assert permissions == [
        {"xuid": "12345", "name": "player1", "permission_level": "operator"}
    ]


def test_set_player_permission(real_bedrock_server):
    server = real_bedrock_server
    server.set_player_permission("12345", "operator", "player1")

    permissions_path = server.permissions_json_path
    with open(permissions_path, "r") as f:
        data = json.load(f)
        assert data == [{"permission": "operator", "xuid": "12345", "name": "player1"}]
