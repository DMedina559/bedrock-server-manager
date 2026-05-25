import os
import tempfile
from unittest.mock import MagicMock

import pytest

from bedrock_server_manager.core.server.player_mixin import ServerPlayerMixin


class DummyServer(ServerPlayerMixin):
    def __init__(self, server_log_path):
        self.server_log_path = server_log_path
        self.server_name = "test_server"
        self.logger = MagicMock()
        self._log_file_cursor = 0
        self.players = []


@pytest.fixture
def temp_log_file():
    fd, path = tempfile.mkstemp()
    os.close(fd)
    yield path
    os.remove(path)


def test_update_online_players_basic(temp_log_file):
    with open(temp_log_file, "w") as f:
        f.write("[INFO] Player connected: Steve, xuid: 1234567890\n")
        f.write("[INFO] Player connected: Alex, xuid: 0987654321\n")
        f.write("[INFO] Player disconnected: Steve, xuid: 1234567890\n")
        f.write("[INFO] Other log noise...\n")

    server = DummyServer(temp_log_file)
    players = server.update_online_players()
    assert len(players) == 1
    assert players[0] == {"name": "Alex", "uuid": "0987654321"}

    # Test incremental reading
    with open(temp_log_file, "a") as f:
        f.write("[INFO] Player connected: Steve, xuid: 1234567890\n")

    players = server.update_online_players()
    assert len(players) == 2
    xuids = [p["uuid"] for p in players]
    assert "0987654321" in xuids
    assert "1234567890" in xuids


def test_update_online_players_multiple_connect_disconnect(temp_log_file):
    with open(temp_log_file, "w") as f:
        f.write("[INFO] Player connected: Steve, xuid: 123\n")
        f.write("[INFO] Player disconnected: Steve, xuid: 123\n")
        f.write("[INFO] Player connected: Steve, xuid: 123\n")
        f.write("[INFO] Player connected: Alex, xuid: 456\n")

    server = DummyServer(temp_log_file)
    players = server.update_online_players()
    assert len(players) == 2
    xuids = [p["uuid"] for p in players]
    assert "123" in xuids
    assert "456" in xuids


def test_update_online_players_disconnect_without_connect(temp_log_file):
    # This simulates a case where the server started logging after a player connected
    # or the log got truncated, so we only see a disconnect.
    server = DummyServer(temp_log_file)
    server.players = [
        {"name": "Unknown", "uuid": "999"},
        {"name": "Other", "uuid": "888"},
    ]

    with open(temp_log_file, "w") as f:
        f.write("[INFO] Player disconnected: Unknown, xuid: 999\n")
        f.write("[INFO] Player connected: Steve, xuid: 123\n")

    players = server.update_online_players()
    assert len(players) == 2
    xuids = [p["uuid"] for p in players]
    assert "888" in xuids
    assert "123" in xuids


def test_update_online_players_empty_or_missing_log(temp_log_file):
    server = DummyServer(temp_log_file)
    assert server.update_online_players() == []

    server_missing = DummyServer(temp_log_file + "_missing")
    assert server_missing.update_online_players() == []


def test_update_online_players_special_characters_in_name(temp_log_file):
    with open(temp_log_file, "w") as f:
        f.write("[INFO] Player connected: St3ve_123!, xuid: 123\n")
        f.write("[INFO] Player connected: <Alex> [Pro], xuid: 456\n")

    server = DummyServer(temp_log_file)
    players = server.update_online_players()
    assert len(players) == 2
    names = [p["name"] for p in players]
    assert "St3ve_123!" in names
    assert "<Alex> [Pro]" in names


def test_update_online_players_same_name_different_xuid(temp_log_file):
    with open(temp_log_file, "w") as f:
        f.write("[INFO] Player connected: Steve, xuid: 111\n")
        f.write("[INFO] Player connected: Steve, xuid: 222\n")

    server = DummyServer(temp_log_file)
    players = server.update_online_players()
    assert len(players) == 2
    xuids = [p["uuid"] for p in players]
    assert "111" in xuids
    assert "222" in xuids


def test_update_online_players_malformed_lines(temp_log_file):
    with open(temp_log_file, "w") as f:
        f.write("[INFO] Player connected: Steve xuid: 111\n")  # Missing comma
        f.write("[INFO] Player connected: Alex, xuid: \n")  # Missing xuid
        f.write("[INFO] Player disconnected: Bob, xuid: abc\n")  # Non-numeric xuid
        f.write("[INFO] Player connected: RealPlayer, xuid: 333\n")

    server = DummyServer(temp_log_file)
    players = server.update_online_players()
    # It should only correctly parse the valid line
    assert len(players) == 1
    assert players[0] == {"name": "RealPlayer", "uuid": "333"}


def test_update_online_players_pfid_format(temp_log_file):
    with open(temp_log_file, "w") as f:
        f.write(
            "NO LOG FILE! - [2026-05-24 12:23:40:983 INFO] Player connected: testUser132, xuid: 111333555\n"
        )
        f.write(
            "NO LOG FILE! - [2026-05-24 12:23:53:417 INFO] Player PartyIdUpdate:  pfid: 231IDe23242, partyid: , isLeader: false\n"
        )
        f.write(
            "NO LOG FILE! - [2026-05-24 12:24:01:685 INFO] Player Spawned: testUser132 xuid: 111333555, pfid: 231IDe23242\n"
        )

    server = DummyServer(temp_log_file)
    players = server.update_online_players()
    assert len(players) == 1
    assert players[0] == {"name": "testUser132", "uuid": "111333555"}

    with open(temp_log_file, "a") as f:
        f.write(
            "NO LOG FILE! - [2026-05-24 12:24:30:913 INFO] Player disconnected: testUser132, xuid: 111333555, pfid: 231IDe23242\n"
        )

    players = server.update_online_players()
    assert len(players) == 0
