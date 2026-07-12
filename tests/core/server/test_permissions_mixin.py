import json
import os

import pytest


def test_get_formatted_permissions(real_bedrock_server):
    """Test retrieving formatted permissions including names from a map."""
    server = real_bedrock_server
    permissions_path = server.permissions_json_path

    perm_data = [
        {"permission": "operator", "xuid": "12345"},
        {"permission": "member", "xuid": "67890"},
    ]

    with open(permissions_path, "w") as f:
        json.dump(perm_data, f)

    name_map = {"12345": "player1"}
    formatted = server.get_formatted_permissions(name_map)

    assert len(formatted) == 2
    # Sort order: 'p' comes before 'u' (player1 vs Unknown)
    assert formatted[0]["xuid"] == "12345"
    assert formatted[0]["permission_level"] == "operator"
    assert formatted[0]["name"] == "player1"

    assert formatted[1]["xuid"] == "67890"
    assert formatted[1]["permission_level"] == "member"
    assert formatted[1]["name"] == "Unknown (XUID: 67890)"


def test_set_player_permission_new_player(real_bedrock_server):
    """Test setting permission for a new player."""
    server = real_bedrock_server
    server.set_player_permission("12345", "operator", "player1")

    permissions_path = server.permissions_json_path
    with open(permissions_path, "r") as f:
        data = json.load(f)
        assert len(data) == 1
        assert data[0] == {"permission": "operator", "xuid": "12345", "name": "player1"}


def test_set_player_permission_update_existing(real_bedrock_server):
    """Test updating permission for an existing player."""
    server = real_bedrock_server
    permissions_path = server.permissions_json_path
    perm_data = [{"permission": "member", "xuid": "12345", "name": "existing"}]
    with open(permissions_path, "w") as f:
        json.dump(perm_data, f)

    server.set_player_permission("12345", "operator")

    with open(permissions_path, "r") as f:
        data = json.load(f)
        assert len(data) == 1
        assert data[0]["permission"] == "operator"
        assert data[0]["xuid"] == "12345"


def test_set_player_permission_visitor(real_bedrock_server):
    """Test setting permission to visitor updates them in the list."""
    server = real_bedrock_server
    permissions_path = server.permissions_json_path
    perm_data = [{"permission": "operator", "xuid": "12345"}]
    with open(permissions_path, "w") as f:
        json.dump(perm_data, f)

    server.set_player_permission("12345", "visitor")

    with open(permissions_path, "r") as f:
        data = json.load(f)
        assert len(data) == 1
        assert data[0]["permission"] == "visitor"


def test_set_player_permission_unwritable_file(real_bedrock_server):
    """Test setting permission fails gracefully if file is unwritable."""
    server = real_bedrock_server
    permissions_path = server.permissions_json_path
    with open(permissions_path, "w") as f:
        f.write("[]")

    os.chmod(permissions_path, 0o444)
    try:
        with pytest.raises(Exception):
            server.set_player_permission("12345", "operator")
    finally:
        os.chmod(permissions_path, 0o644)
