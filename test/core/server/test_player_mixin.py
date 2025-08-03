import pytest
import os
import shutil
import tempfile
from unittest.mock import patch

from bedrock_server_manager.core.server.player_mixin import ServerPlayerMixin
from bedrock_server_manager.core.server.base_server_mixin import BedrockServerBaseMixin
from bedrock_server_manager.config.settings import Settings


def test_scan_log_for_players_success(real_bedrock_server):
    server = real_bedrock_server
    log_path = os.path.join(server.server_dir, "server_output.txt")
    with open(log_path, "w") as f:
        f.write("Player connected: Player1, xuid: 123\n")
        f.write("Player connected: Player2, xuid: 456\n")

    players = server.scan_log_for_players()
    assert len(players) == 2
    assert {"name": "Player1", "xuid": "123"} in players
    assert {"name": "Player2", "xuid": "456"} in players


def test_scan_log_for_players_no_log(real_bedrock_server):
    server = real_bedrock_server
    log_path = server.server_log_path
    with open(log_path, "w") as f:
        f.write("test")
    os.remove(log_path)
    players = server.scan_log_for_players()
    assert players == []


def test_scan_log_for_players_empty_log(real_bedrock_server):
    server = real_bedrock_server
    log_path = os.path.join(server.server_dir, "server_output.txt")
    with open(log_path, "w") as f:
        pass
    players = server.scan_log_for_players()
    assert players == []


def test_scan_log_for_players_no_player_entries(real_bedrock_server):
    server = real_bedrock_server
    log_path = os.path.join(server.server_dir, "server_output.txt")
    with open(log_path, "w") as f:
        f.write("Server starting...\n")
    players = server.scan_log_for_players()
    assert players == []


def test_scan_log_for_players_malformed_entries(real_bedrock_server):
    server = real_bedrock_server
    log_path = os.path.join(server.server_dir, "server_output.txt")
    with open(log_path, "w") as f:
        f.write("Player connected: Player1, xuid: \n")  # malformed
        f.write("Player connected: , xuid: 123\n")  # malformed
    players = server.scan_log_for_players()
    assert players == []
