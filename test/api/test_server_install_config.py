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
def mock_bedrock_server():
    """Fixture for a mocked BedrockServer."""
    server = MagicMock()
    server.add_to_allowlist.return_value = 1
    server.get_allowlist.return_value = [{"name": "player1", "xuid": "123"}]
    server.remove_from_allowlist.return_value = True
    server.get_formatted_permissions.return_value = [
        {"name": "player1", "xuid": "123", "permission_level": "operator"}
    ]
    server.get_server_properties.return_value = {"level-name": "world"}
    server.get_target_version.return_value = "1.0.0"
    server.is_update_needed.return_value = True
    server.get_version.return_value = "1.0.0"
    return server


@pytest.fixture
def mock_get_server_instance(mock_bedrock_server):
    """Fixture to patch get_server_instance."""
    with patch(
        "bedrock_server_manager.api.server_install_config.get_server_instance",
        return_value=mock_bedrock_server,
    ) as mock:
        yield mock


class TestAllowlist:
    def test_add_players_to_allowlist_api(self, mock_get_server_instance):
        result = add_players_to_allowlist_api(
            "test-server", [{"name": "player2", "xuid": "456"}]
        )
        assert result["status"] == "success"
        assert result["added_count"] == 1

    def test_get_server_allowlist_api(self, mock_get_server_instance):
        result = get_server_allowlist_api("test-server")
        assert result["status"] == "success"
        assert len(result["players"]) == 1

    def test_remove_players_from_allowlist(self, mock_get_server_instance):
        result = remove_players_from_allowlist("test-server", ["player1"])
        assert result["status"] == "success"
        assert result["details"]["removed"] == ["player1"]


class TestPermissions:
    def test_configure_player_permission(self, mock_get_server_instance):
        result = configure_player_permission(
            "test-server", "123", "player1", "operator"
        )
        assert result["status"] == "success"

    def test_get_server_permissions_api(self, mock_get_server_instance):
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


class TestProperties:
    def test_get_server_properties_api(self, mock_get_server_instance):
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
    def test_modify_server_properties(
        self, mock_lifecycle, mock_get_server_instance, mock_bedrock_server
    ):
        result = modify_server_properties("test-server", {"level-name": "new-world"})
        assert result["status"] == "success"
        mock_lifecycle.assert_called_once()
        mock_bedrock_server.set_server_property.assert_called_once_with(
            "level-name", "new-world"
        )


class TestInstallUpdate:
    @patch(
        "bedrock_server_manager.api.server_install_config.validate_server_name_format"
    )
    @patch("os.path.exists", return_value=False)
    def test_install_new_server(
        self,
        mock_exists,
        mock_validate,
        mock_get_server_instance,
        mock_bedrock_server,
        mocker,
    ):
        mock_validate.return_value = {"status": "success"}
        mock_get_settings_instance = mocker.patch(
            "bedrock_server_manager.api.server_install_config.get_settings_instance"
        )
        mock_get_settings_instance.return_value.get.return_value = "/servers"
        result = install_new_server("new-server")
        assert result["status"] == "success"
        mock_bedrock_server.install_or_update.assert_called_once()

    @patch("bedrock_server_manager.api.server_install_config.server_lifecycle_manager")
    def test_update_server(
        self, mock_lifecycle, mock_get_server_instance, mock_bedrock_server
    ):
        result = update_server("test-server")
        assert result["status"] == "success"
        assert result["updated"] is True
        mock_lifecycle.assert_called_once()
        mock_bedrock_server.backup_all_data.assert_called_once()
        mock_bedrock_server.install_or_update.assert_called_once()
