import pytest
from unittest.mock import patch, MagicMock

from bedrock_server_manager.api.player import (
    add_players_manually_api,
    get_all_known_players_api,
    scan_and_update_player_db_api,
)
from bedrock_server_manager.error import UserInputError, BSMError


class TestPlayerManagement:
    def test_add_players_manually_api_success(self, app_context):
        with patch.object(
            app_context.manager, "save_player_data", return_value=1
        ) as mock_save:
            result = add_players_manually_api(["player1:123"], app_context=app_context)
            assert result["status"] == "success"
            assert result["count"] == 1
            mock_save.assert_called_once()

    def test_add_players_manually_api_empty_list(self, app_context):
        result = add_players_manually_api([], app_context=app_context)
        assert result["status"] == "error"
        assert "non-empty list" in result["message"]

    def test_add_players_manually_api_invalid_string(self, app_context):
        with patch.object(
            app_context.manager,
            "parse_player_cli_argument",
            side_effect=UserInputError("Invalid format"),
        ):
            result = add_players_manually_api(
                ["invalid-player"], app_context=app_context
            )
            assert result["status"] == "error"
            assert "Invalid player data" in result["message"]

    def test_get_all_known_players_api(self, app_context, db_session):
        from bedrock_server_manager.db.models import Player

        db_session.add(Player(player_name="player1", xuid="123"))
        db_session.commit()

        result = get_all_known_players_api(app_context=app_context)
        assert result["status"] == "success"
        assert len(result["players"]) == 1
        assert result["players"][0]["name"] == "player1"

    def test_scan_and_update_player_db_api_success(self, app_context):
        with patch.object(
            app_context.manager,
            "discover_and_store_players_from_all_server_logs",
            return_value={
                "total_entries_in_logs": 1,
                "unique_players_submitted_for_saving": 1,
                "actually_saved_or_updated_in_db": 1,
                "scan_errors": [],
            },
        ) as mock_discover:
            result = scan_and_update_player_db_api(app_context=app_context)
            assert result["status"] == "success"
            assert "Player DB update complete" in result["message"]
            assert result["details"]["actually_saved_or_updated_in_db"] == 1
            mock_discover.assert_called_once()

    def test_scan_and_update_player_db_api_bsm_error(self, app_context):
        with patch.object(
            app_context.manager,
            "discover_and_store_players_from_all_server_logs",
            side_effect=BSMError("Test error"),
        ):
            result = scan_and_update_player_db_api(app_context=app_context)
            assert result["status"] == "error"
            assert "Test error" in result["message"]
