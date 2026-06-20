import json
import os
import shutil

import pytest


def test_get_allowlist(real_bedrock_server):
    server = real_bedrock_server
    allowlist_path = server.allowlist_json_path
    allowlist_data = [{"name": "player1", "xuid": "12345", "ignoresPlayerLimit": False}]
    with open(allowlist_path, "w") as f:
        json.dump(allowlist_data, f)

    allowlist = server.get_allowlist()
    assert allowlist == allowlist_data


def test_add_to_allowlist(real_bedrock_server):
    server = real_bedrock_server
    allowlist_data = [{"name": "player1", "xuid": "12345"}]
    server.add_to_allowlist(allowlist_data)

    allowlist_path = server.allowlist_json_path
    with open(allowlist_path, "r") as f:
        data = json.load(f)
        assert data == [
            {"name": "player1", "xuid": "12345", "ignoresPlayerLimit": False}
        ]


def test_get_allowlist_missing_file(real_bedrock_server):
    server = real_bedrock_server
    allowlist = server.get_allowlist()
    assert allowlist == []


def test_get_allowlist_empty_file(real_bedrock_server):
    server = real_bedrock_server
    allowlist_path = server.allowlist_json_path
    with open(allowlist_path, "w") as f:
        f.write("")

    allowlist = server.get_allowlist()
    assert allowlist == []


def test_get_allowlist_invalid_json(real_bedrock_server):
    server = real_bedrock_server
    allowlist_path = server.allowlist_json_path
    with open(allowlist_path, "w") as f:
        f.write("{invalid_json}")

    with pytest.raises(Exception):
        server.get_allowlist()


def test_get_allowlist_json_object(real_bedrock_server):
    server = real_bedrock_server
    allowlist_path = server.allowlist_json_path
    with open(allowlist_path, "w") as f:
        json.dump({"key": "value"}, f)

    allowlist = server.get_allowlist()
    assert allowlist == []


def test_get_allowlist_missing_server_dir(real_bedrock_server):
    server = real_bedrock_server
    shutil.rmtree(server.server_dir)
    with pytest.raises(Exception):
        server.get_allowlist()


def test_add_to_allowlist_non_existent_file(real_bedrock_server):
    server = real_bedrock_server
    players_to_add = [{"name": "player2", "xuid": "67890"}]
    server.add_to_allowlist(players_to_add)
    allowlist = server.get_allowlist()
    assert any(p["name"] == "player2" for p in allowlist)


def test_add_to_allowlist_player_already_exists(real_bedrock_server):
    server = real_bedrock_server
    players_to_add = [{"name": "player1", "xuid": "12345"}]
    server.add_to_allowlist(players_to_add)
    result = server.add_to_allowlist(players_to_add)
    assert result == 0


def test_add_to_allowlist_invalid_entry(real_bedrock_server):
    server = real_bedrock_server
    players_to_add = ["invalid_entry"]
    server.add_to_allowlist(players_to_add)
    allowlist = server.get_allowlist()
    assert len(allowlist) == 0


def test_add_to_allowlist_missing_name(real_bedrock_server):
    server = real_bedrock_server
    players_to_add = [{"xuid": "12345"}]
    server.add_to_allowlist(players_to_add)
    allowlist = server.get_allowlist()
    assert len(allowlist) == 0


def test_add_to_allowlist_multiple_players(real_bedrock_server):
    server = real_bedrock_server
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


def test_add_to_allowlist_unwritable_file(real_bedrock_server):
    server = real_bedrock_server
    allowlist_path = server.allowlist_json_path
    with open(allowlist_path, "w") as f:
        f.write("[]")
    os.chmod(allowlist_path, 0o444)  # Read-only
    players_to_add = [{"name": "player2", "xuid": "67890"}]
    with pytest.raises(Exception):
        server.add_to_allowlist(players_to_add)
    os.chmod(allowlist_path, 0o644)


def test_remove_from_allowlist_player_not_found(real_bedrock_server):
    server = real_bedrock_server
    result = server.remove_from_allowlist("non_existent_player")
    assert result is False


def test_remove_from_allowlist_empty_file(real_bedrock_server):
    server = real_bedrock_server
    result = server.remove_from_allowlist("player1")
    assert result is False


def test_remove_from_allowlist_unwritable_file(real_bedrock_server):
    server = real_bedrock_server
    players_to_add = [{"name": "player1", "xuid": "12345"}]
    server.add_to_allowlist(players_to_add)
    allowlist_path = server.allowlist_json_path
    os.chmod(allowlist_path, 0o444)  # Read-only
    with pytest.raises(Exception):
        server.remove_from_allowlist("player1")
    os.chmod(allowlist_path, 0o644)
