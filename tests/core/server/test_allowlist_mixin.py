import json
import os

import pytest


def test_get_allowlist(real_bedrock_server):
    """Test retrieving allowlist from file."""
    server = real_bedrock_server
    allowlist_path = server.allowlist_json_path
    allowlist_data = [{"name": "player1", "xuid": "12345", "ignoresPlayerLimit": False}]
    with open(allowlist_path, "w") as f:
        json.dump(allowlist_data, f)

    allowlist = server.get_allowlist()
    assert allowlist == allowlist_data


def test_get_allowlist_missing_file(real_bedrock_server):
    """Test retrieving allowlist when file doesn't exist returns empty list."""
    server = real_bedrock_server
    allowlist = server.get_allowlist()
    assert allowlist == []


def test_get_allowlist_empty_file(real_bedrock_server):
    """Test retrieving allowlist from empty file returns empty list."""
    server = real_bedrock_server
    allowlist_path = server.allowlist_json_path
    with open(allowlist_path, "w") as f:
        f.write("")

    allowlist = server.get_allowlist()
    assert allowlist == []


def test_get_allowlist_invalid_json(real_bedrock_server):
    """Test retrieving allowlist handles invalid json properly (raises error)."""
    server = real_bedrock_server
    allowlist_path = server.allowlist_json_path
    with open(allowlist_path, "w") as f:
        f.write("{invalid_json}")

    with pytest.raises(Exception):
        server.get_allowlist()


def test_get_allowlist_json_object(real_bedrock_server):
    """Test retrieving allowlist if it is a JSON object instead of a list."""
    server = real_bedrock_server
    allowlist_path = server.allowlist_json_path
    with open(allowlist_path, "w") as f:
        json.dump({"key": "value"}, f)

    allowlist = server.get_allowlist()
    assert allowlist == []  # Fallbacks to empty list based on legacy tests


def test_add_to_allowlist(real_bedrock_server):
    """Test adding a player to the allowlist."""
    server = real_bedrock_server
    allowlist_data = [{"name": "player1", "xuid": "12345"}]
    server.add_to_allowlist(allowlist_data)

    allowlist_path = server.allowlist_json_path
    with open(allowlist_path, "r") as f:
        data = json.load(f)
        assert data == [
            {"name": "player1", "xuid": "12345", "ignoresPlayerLimit": False}
        ]


def test_add_to_allowlist_non_existent_file(real_bedrock_server):
    """Test adding to allowlist creates the file if it doesn't exist."""
    server = real_bedrock_server
    if os.path.exists(server.allowlist_json_path):
        os.remove(server.allowlist_json_path)

    players_to_add = [{"name": "player2", "xuid": "67890"}]
    server.add_to_allowlist(players_to_add)
    allowlist = server.get_allowlist()
    assert len(allowlist) == 1
    assert allowlist[0]["name"] == "player2"


def test_add_to_allowlist_player_already_exists(real_bedrock_server):
    """Test adding a player that already exists returns 0 added."""
    server = real_bedrock_server
    players_to_add = [{"name": "player1", "xuid": "12345"}]
    server.add_to_allowlist(players_to_add)

    result = server.add_to_allowlist(players_to_add)
    assert result == 0


def test_add_to_allowlist_invalid_entry(real_bedrock_server):
    """Test adding an invalid entry (non-dict) to allowlist."""
    server = real_bedrock_server
    players_to_add = ["invalid_entry"]
    server.add_to_allowlist(players_to_add)  # type: ignore
    allowlist = server.get_allowlist()
    assert len(allowlist) == 0


def test_add_to_allowlist_missing_name(real_bedrock_server):
    """Test adding an entry without a name."""
    server = real_bedrock_server
    players_to_add = [{"xuid": "12345"}]
    server.add_to_allowlist(players_to_add)
    allowlist = server.get_allowlist()
    assert len(allowlist) == 0


def test_add_to_allowlist_multiple_players(real_bedrock_server):
    """Test adding multiple players including duplicates."""
    server = real_bedrock_server
    players_to_add = [
        {"name": "player2", "xuid": "67890"},
        {"name": "player3", "xuid": "54321"},
        {
            "name": "player2",
            "xuid": "09876",
        },  # Duplicate name but diff xuid usually ignored by name
    ]
    added = server.add_to_allowlist(players_to_add)
    allowlist = server.get_allowlist()
    assert added == 2
    assert len(allowlist) == 2
    assert any(p["name"] == "player2" for p in allowlist)
    assert any(p["name"] == "player3" for p in allowlist)


def test_add_to_allowlist_unwritable_file(real_bedrock_server):
    """Test adding to a read-only allowlist file."""
    server = real_bedrock_server
    allowlist_path = server.allowlist_json_path
    with open(allowlist_path, "w") as f:
        f.write("[]")

    os.chmod(allowlist_path, 0o444)  # Read-only
    players_to_add = [{"name": "player2", "xuid": "67890"}]

    try:
        with pytest.raises(Exception):
            server.add_to_allowlist(players_to_add)
    finally:
        os.chmod(allowlist_path, 0o644)


def test_remove_from_allowlist_player_not_found(real_bedrock_server):
    """Test removing a non-existent player."""
    server = real_bedrock_server
    result = server.remove_from_allowlist("non_existent_player")
    assert result is False


def test_remove_from_allowlist_empty_file(real_bedrock_server):
    """Test removing from an empty allowlist."""
    server = real_bedrock_server
    result = server.remove_from_allowlist("player1")
    assert result is False


def test_remove_from_allowlist_success(real_bedrock_server):
    """Test successfully removing a player."""
    server = real_bedrock_server
    players_to_add = [{"name": "player1", "xuid": "12345"}]
    server.add_to_allowlist(players_to_add)

    result = server.remove_from_allowlist("player1")
    assert result is True
    assert len(server.get_allowlist()) == 0


def test_remove_from_allowlist_unwritable_file(real_bedrock_server):
    """Test removing from a read-only allowlist file."""
    server = real_bedrock_server
    players_to_add = [{"name": "player1", "xuid": "12345"}]
    server.add_to_allowlist(players_to_add)

    allowlist_path = server.allowlist_json_path
    os.chmod(allowlist_path, 0o444)  # Read-only

    try:
        with pytest.raises(Exception):
            server.remove_from_allowlist("player1")
    finally:
        os.chmod(allowlist_path, 0o644)
