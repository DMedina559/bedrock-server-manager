import pytest
import os
import shutil
import tempfile
from bedrock_server_manager.core.server.player_mixin import ServerPlayerMixin
from bedrock_server_manager.core.server.base_server_mixin import BedrockServerBaseMixin
from bedrock_server_manager.config.settings import Settings


class SetupBedrockServer(ServerPlayerMixin, BedrockServerBaseMixin):
    def run_command(self, command):
        pass


@pytest.fixture
def player_mixin_fixture():
    temp_dir = tempfile.mkdtemp()
    server_name = "test_server"
    settings = Settings()
    settings.set("paths.servers", os.path.join(temp_dir, "servers"))

    server = SetupBedrockServer(server_name=server_name, settings_instance=settings)
    os.makedirs(server.server_dir, exist_ok=True)

    yield server, temp_dir

    shutil.rmtree(temp_dir)


# The get_online_players method is not part of the player mixin, so these tests are removed.


def test_scan_log_for_players_success(player_mixin_fixture):
    server, _ = player_mixin_fixture
    log_path = os.path.join(server.server_dir, "server_output.txt")
    with open(log_path, "w") as f:
        f.write("Player connected: Player1, xuid: 123\n")
        f.write("Player connected: Player2, xuid: 456\n")

    players = server.scan_log_for_players()
    assert len(players) == 2
    assert {"name": "Player1", "xuid": "123"} in players
    assert {"name": "Player2", "xuid": "456"} in players


def test_scan_log_for_players_no_log(player_mixin_fixture):
    server, _ = player_mixin_fixture
    players = server.scan_log_for_players()
    assert players == []


def test_scan_log_for_players_empty_log(player_mixin_fixture):
    server, _ = player_mixin_fixture
    log_path = os.path.join(server.server_dir, "server.log")
    with open(log_path, "w") as f:
        pass
    players = server.scan_log_for_players()
    assert players == []


def test_scan_log_for_players_no_player_entries(player_mixin_fixture):
    server, _ = player_mixin_fixture
    log_path = os.path.join(server.server_dir, "server.log")
    with open(log_path, "w") as f:
        f.write("Server starting...\n")
    players = server.scan_log_for_players()
    assert players == []


def test_scan_log_for_players_malformed_entries(player_mixin_fixture):
    server, _ = player_mixin_fixture
    log_path = os.path.join(server.server_dir, "server_output.txt")
    with open(log_path, "w") as f:
        f.write("Player connected: Player1, xuid: \n")  # malformed
        f.write("Player connected: , xuid: 123\n")  # malformed
    players = server.scan_log_for_players()
    assert players == []
