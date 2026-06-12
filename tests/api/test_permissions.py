import json
import os
from unittest.mock import patch

from bedrock_server_manager.api.permissions import (
    get_permissions,
    set_permissions,
)


class TestPermissions:
    def test_set_permissions(self, app_context):
        server = app_context.get_server("test_server")
        result = set_permissions(
            "test_server", "123", "player1", "operator", app_context=app_context
        )
        assert result["status"] == "success"

        # Check the permissions file
        permissions_path = os.path.join(server.server_dir, "permissions.json")
        with open(permissions_path, "r") as f:
            permissions_data = json.load(f)

        assert len(permissions_data) == 1
        assert permissions_data[0]["xuid"] == "123"

    def test_get_permissions(self, app_context):
        server = app_context.get_server("test_server")
        # Add a permission to the permissions file first
        permissions_path = os.path.join(server.server_dir, "permissions.json")
        with open(permissions_path, "w") as f:
            json.dump([{"xuid": "123", "permission": "operator", "name": "player1"}], f)

        with patch(
            "bedrock_server_manager.api.permissions.player_api.get_all_known_players_api"
        ) as mock_get_players:
            mock_get_players.return_value = {
                "status": "success",
                "players": [{"name": "player1", "xuid": "123"}],
            }
            result = get_permissions("test_server", app_context=app_context)
            assert result["status"] == "success"
            assert len(result["permissions"]) == 1
            assert result["permissions"][0]["name"] == "player1"
