import json
import os

from bedrock_server_manager.api.allowlist import (
    add_to_allowlist,
    get_allowlist,
    remove_from_allowlist,
)


class TestAllowlist:
    def test_add_to_allowlist(self, app_context):
        server = app_context.get_server("test_server")
        result = add_to_allowlist(
            "test_server", [{"name": "player2", "xuid": "456"}], app_context=app_context
        )
        assert result["status"] == "success"
        assert result["added_count"] == 1

        # Check the allowlist file
        allowlist_path = os.path.join(server.server_dir, "allowlist.json")
        with open(allowlist_path, "r") as f:
            allowlist_data = json.load(f)

        assert len(allowlist_data) == 1
        assert allowlist_data[0]["name"] == "player2"

    def test_get_allowlist(self, app_context):
        server = app_context.get_server("test_server")
        # Add a player to the allowlist first
        allowlist_path = os.path.join(server.server_dir, "allowlist.json")
        with open(allowlist_path, "w") as f:
            json.dump([{"name": "player1", "xuid": "123"}], f)

        result = get_allowlist("test_server", app_context=app_context)
        assert result["status"] == "success"
        assert len(result["players"]) == 1
        assert result["players"][0]["name"] == "player1"

    def test_remove_from_allowlist(self, app_context):
        server = app_context.get_server("test_server")
        # Add a player to the allowlist first
        allowlist_path = os.path.join(server.server_dir, "allowlist.json")
        with open(allowlist_path, "w") as f:
            json.dump([{"name": "player1", "xuid": "123"}], f)

        result = remove_from_allowlist(
            "test_server", ["player1"], app_context=app_context
        )
        assert result["status"] == "success"
        assert result["details"]["removed"] == ["player1"]

        # Check the allowlist file
        with open(allowlist_path, "r") as f:
            allowlist_data = json.load(f)

        assert len(allowlist_data) == 0
