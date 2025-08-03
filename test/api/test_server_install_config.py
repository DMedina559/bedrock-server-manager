import pytest
from unittest.mock import patch, MagicMock

from bedrock_server_manager.api.server_install_config import (
    add_players_to_allowlist_api,
    get_server_allowlist_api,
    remove_players_from_allowlist,
    configure_player_permission,
    get_server_permissions_api,
    get_server_properties_api,
    validate_server_property_value,
    modify_server_properties,
    install_new_server,
    update_server,
)
from bedrock_server_manager.error import UserInputError


@pytest.fixture
def mock_get_server_instance(mocker, mock_bedrock_server):
    """Fixture to patch get_server_instance for the api.server_install_config module."""
    mock_bedrock_server.add_to_allowlist.return_value = 1
    mock_bedrock_server.get_allowlist.return_value = [
        {"name": "player1", "xuid": "123"}
    ]
    mock_bedrock_server.remove_from_allowlist.return_value = True
    mock_bedrock_server.get_formatted_permissions.return_value = [
        {"name": "player1", "xuid": "123", "permission_level": "operator"}
    ]
    mock_bedrock_server.get_server_properties.return_value = {"level-name": "world"}
    mock_bedrock_server.get_target_version.return_value = "1.0.0"
    mock_bedrock_server.is_update_needed.return_value = True
    mock_bedrock_server.get_version.return_value = "1.0.0"

    return mocker.patch(
        "bedrock_server_manager.api.server_install_config.get_server_instance",
        return_value=mock_bedrock_server,
    )


import os
import json


class TestAllowlist:
    def test_add_players_to_allowlist_api(self, real_bedrock_server):
        with patch(
            "bedrock_server_manager.api.server_install_config.get_server_instance",
            return_value=real_bedrock_server,
        ):
            result = add_players_to_allowlist_api(
                "test-server", [{"name": "player2", "xuid": "456"}]
            )
            assert result["status"] == "success"
            assert result["added_count"] == 1

            # Check the allowlist file
            allowlist_path = os.path.join(
                real_bedrock_server.server_dir, "allowlist.json"
            )
            with open(allowlist_path, "r") as f:
                allowlist_data = json.load(f)

            assert len(allowlist_data) == 1
            assert allowlist_data[0]["name"] == "player2"

    def test_get_server_allowlist_api(self, real_bedrock_server):
        # Add a player to the allowlist first
        allowlist_path = os.path.join(real_bedrock_server.server_dir, "allowlist.json")
        with open(allowlist_path, "w") as f:
            json.dump([{"name": "player1", "xuid": "123"}], f)

        with patch(
            "bedrock_server_manager.api.server_install_config.get_server_instance",
            return_value=real_bedrock_server,
        ):
            result = get_server_allowlist_api("test-server")
            assert result["status"] == "success"
            assert len(result["players"]) == 1
            assert result["players"][0]["name"] == "player1"

    def test_remove_players_from_allowlist(self, real_bedrock_server):
        # Add a player to the allowlist first
        allowlist_path = os.path.join(real_bedrock_server.server_dir, "allowlist.json")
        with open(allowlist_path, "w") as f:
            json.dump([{"name": "player1", "xuid": "123"}], f)

        with patch(
            "bedrock_server_manager.api.server_install_config.get_server_instance",
            return_value=real_bedrock_server,
        ):
            result = remove_players_from_allowlist("test-server", ["player1"])
            assert result["status"] == "success"
            assert result["details"]["removed"] == ["player1"]

            # Check the allowlist file
            with open(allowlist_path, "r") as f:
                allowlist_data = json.load(f)

            assert len(allowlist_data) == 0


class TestPermissions:
    def test_configure_player_permission(self, real_bedrock_server):
        with patch(
            "bedrock_server_manager.api.server_install_config.get_server_instance",
            return_value=real_bedrock_server,
        ):
            result = configure_player_permission(
                "test-server", "123", "player1", "operator"
            )
            assert result["status"] == "success"

            # Check the permissions file
            permissions_path = os.path.join(
                real_bedrock_server.server_dir, "permissions.json"
            )
            with open(permissions_path, "r") as f:
                permissions_data = json.load(f)

            assert len(permissions_data) == 1
            assert permissions_data[0]["xuid"] == "123"

    def test_get_server_permissions_api(self, real_bedrock_server):
        # Add a permission to the permissions file first
        permissions_path = os.path.join(
            real_bedrock_server.server_dir, "permissions.json"
        )
        with open(permissions_path, "w") as f:
            json.dump([{"xuid": "123", "permission": "operator", "name": "player1"}], f)

        with patch(
            "bedrock_server_manager.api.server_install_config.get_server_instance",
            return_value=real_bedrock_server,
        ):
            with patch(
                "bedrock_server_manager.api.server_install_config.player_api.get_all_known_players_api"
            ) as mock_get_players:
                mock_get_players.return_value = {
                    "status": "success",
                    "players": [{"name": "player1", "xuid": "123"}],
                }
                result = get_server_permissions_api("test-server")
                assert result["status"] == "success"
                assert len(result["data"]["permissions"]) == 1
                assert result["data"]["permissions"][0]["name"] == "player1"


class TestProperties:
    def test_get_server_properties_api(self, real_bedrock_server):
        with patch(
            "bedrock_server_manager.api.server_install_config.get_server_instance",
            return_value=real_bedrock_server,
        ):
            result = get_server_properties_api("test-server")
            assert result["status"] == "success"
            assert result["properties"]["level-name"] == "world"

    def test_validate_server_property_value(self):
        assert (
            validate_server_property_value("level-name", "valid-world")["status"]
            == "success"
        )
        assert (
            validate_server_property_value("level-name", "invalid world!")["status"]
            == "error"
        )

    @patch("bedrock_server_manager.api.server_install_config.server_lifecycle_manager")
    def test_modify_server_properties(self, mock_lifecycle, real_bedrock_server):
        with patch(
            "bedrock_server_manager.api.server_install_config.get_server_instance",
            return_value=real_bedrock_server,
        ):
            result = modify_server_properties(
                "test-server", {"level-name": "new-world"}
            )
            assert result["status"] == "success"
            mock_lifecycle.assert_called_once()

            # Check the server.properties file
            properties = real_bedrock_server.get_server_properties()
            assert properties["level-name"] == "new-world"


class TestInstallUpdate:
    @patch(
        "bedrock_server_manager.api.server_install_config.validate_server_name_format"
    )
    @patch("os.path.exists", return_value=False)
    def test_install_new_server(
        self, mock_exists, mock_validate, real_bedrock_server, mocker
    ):
        mock_validate.return_value = {"status": "success"}
        mock_get_settings_instance = mocker.patch(
            "bedrock_server_manager.api.server_install_config.get_settings_instance"
        )
        mock_get_settings_instance.return_value.get.return_value = "/servers"
        with patch.object(real_bedrock_server, "install_or_update") as mock_install:
            with patch(
                "bedrock_server_manager.api.server_install_config.get_server_instance",
                return_value=real_bedrock_server,
            ):
                result = install_new_server("new-server")
                assert result["status"] == "success"
                mock_install.assert_called_once()

    @patch("bedrock_server_manager.api.server_install_config.server_lifecycle_manager")
    def test_update_server(self, mock_lifecycle, real_bedrock_server):
        with patch.object(real_bedrock_server, "is_update_needed", return_value=True):
            with patch.object(real_bedrock_server, "backup_all_data") as mock_backup:
                with patch.object(
                    real_bedrock_server, "install_or_update"
                ) as mock_install:
                    with patch(
                        "bedrock_server_manager.api.server_install_config.get_server_instance",
                        return_value=real_bedrock_server,
                    ):
                        result = update_server("test-server")
                        assert result["status"] == "success"
                        assert result["updated"] is True
                        mock_lifecycle.assert_called_once()
                        mock_backup.assert_called_once()
                        mock_install.assert_called_once()
