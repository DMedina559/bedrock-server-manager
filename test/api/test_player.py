import pytest
from unittest.mock import patch, MagicMock

from bedrock_server_manager.api.player import (
    add_players_manually_api,
    get_all_known_players_api,
    scan_and_update_player_db_api,
)
from bedrock_server_manager.error import UserInputError, BSMError


@pytest.fixture
def mock_get_manager_instance(mocker, mock_bedrock_server_manager):
    """Fixture to patch get_manager_instance for the api.player module."""
    mock_bedrock_server_manager.parse_player_cli_argument.return_value = None
    mock_bedrock_server_manager.save_player_data.return_value = 1
    mock_bedrock_server_manager.get_known_players.return_value = [
        {"name": "player1", "xuid": "123"}
    ]
    mock_bedrock_server_manager.discover_and_store_players_from_all_server_logs.return_value = {
        "total_entries_in_logs": 1,
        "unique_players_submitted_for_saving": 1,
        "actually_saved_or_updated_in_db": 1,
        "scan_errors": [],
    }
    return mocker.patch(
        "bedrock_server_manager.api.player.get_manager_instance",
        return_value=mock_bedrock_server_manager,
        autospec=True,
    )


class TestPlayerManagement:
    def test_add_players_manually_api_success(self, mock_get_manager_instance):
        result = add_players_manually_api(["player1:123"])
        assert result["status"] == "success"
        assert result["count"] == 1
        mock_get_manager_instance.return_value.parse_player_cli_argument.assert_called_once_with(
            "player1:123"
        )

    def test_add_players_manually_api_empty_list(self, mock_get_manager_instance):
        result = add_players_manually_api([])
        assert result["status"] == "error"
        assert "non-empty list" in result["message"]

    def test_add_players_manually_api_invalid_string(self, mock_get_manager_instance):
        mock_get_manager_instance.return_value.parse_player_cli_argument.side_effect = (
            UserInputError("Invalid format")
        )
        result = add_players_manually_api(["invalid-player"])
        assert result["status"] == "error"
        assert "Invalid player data" in result["message"]

    def test_get_all_known_players_api(self, mock_get_manager_instance):
        result = get_all_known_players_api()
        assert result["status"] == "success"
        assert len(result["players"]) == 1
        assert result["players"][0]["name"] == "player1"

    def test_scan_and_update_player_db_api_success(self, mock_get_manager_instance):
        result = scan_and_update_player_db_api()
        assert result["status"] == "success"
        assert "Player DB update complete" in result["message"]
        assert result["details"]["actually_saved_or_updated_in_db"] == 1

    def test_scan_and_update_player_db_api_bsm_error(self, mock_get_manager_instance):
        mock_get_manager_instance.return_value.discover_and_store_players_from_all_server_logs.side_effect = BSMError(
            "Test error"
        )
        result = scan_and_update_player_db_api()
        assert result["status"] == "error"
        assert "Test error" in result["message"]
