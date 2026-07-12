from unittest.mock import MagicMock

from bedrock_server_manager.api.player import (
    add_players_manually_api,
    get_all_known_players_api,
    scan_and_update_player_db_api,
)
from bedrock_server_manager.error import BSMError, UserInputError


def test_add_players_manually_api_success(app_context, monkeypatch):
    """Test add_players_manually_api parses input lists and routes saves."""
    mock_save = MagicMock()
    monkeypatch.setattr("bedrock_server_manager.api.player.save_player_data", mock_save)

    result = add_players_manually_api(["user1:1234", "user2:5678"], app_context)

    assert result["status"] == "success"
    assert result["count"] == 2
    mock_save.assert_called_once()


def test_add_players_manually_api_invalid_input(app_context):
    """Test add_players_manually_api catches bad inputs directly."""
    result = add_players_manually_api([], app_context)
    assert result["status"] == "error"
    assert "non-empty list" in result["message"]


def test_add_players_manually_api_parse_error(app_context, monkeypatch):
    """Test add_players_manually_api catches UserInputError from the parse_player_string core util."""

    def mock_parse(*args):
        raise UserInputError("Bad formatting")

    monkeypatch.setattr(
        "bedrock_server_manager.api.player.parse_player_string", mock_parse
    )

    result = add_players_manually_api(["bad_format"], app_context)

    assert result["status"] == "error"
    assert "Invalid player data: Bad formatting" in result["message"]


def test_add_players_manually_api_no_db(app_context, monkeypatch):
    """Test add_players_manually_api errors properly if no db initialized."""
    # We must patch the underlying hidden variable accessed by the property getter
    monkeypatch.setattr(type(app_context), "db", None)
    result = add_players_manually_api(["player1:123"], app_context)
    assert result["status"] == "error"
    assert "not initialized" in result["message"]


def test_get_all_known_players_api_success(app_context, monkeypatch):
    """Test get_all_known_players_api loads generic players array via mock."""
    mock_get = MagicMock(return_value=[{"name": "p1"}, {"name": "p2"}])
    monkeypatch.setattr("bedrock_server_manager.api.player.get_known_players", mock_get)

    result = get_all_known_players_api(app_context)

    assert result["status"] == "success"
    assert len(result["players"]) == 2


def test_get_all_known_players_api_no_db(app_context, monkeypatch):
    """Test get_all_known_players_api errors properly if no db initialized."""
    monkeypatch.setattr(type(app_context), "db", None)
    result = get_all_known_players_api(app_context)
    assert result["status"] == "error"
    assert "not initialized" in result["message"]


def test_scan_and_update_player_db_api_success(app_context, monkeypatch):
    """Test scan_and_update_player_db_api delegates correctly generating complex stats mapping."""
    mock_discover = MagicMock(
        return_value={
            "total_entries_in_logs": 5,
            "unique_players_submitted_for_saving": 2,
            "actually_saved_or_updated_in_db": 1,
            "scan_errors": [],
        }
    )
    monkeypatch.setattr(
        "bedrock_server_manager.api.player.discover_and_store_players", mock_discover
    )

    result = scan_and_update_player_db_api(app_context)

    assert result["status"] == "success"
    assert result["details"]["actually_saved_or_updated_in_db"] == 1
    assert "actually saved/updated" in result["message"].lower()


def test_scan_and_update_player_db_api_bsm_error(app_context, monkeypatch):
    """Test scan_and_update_player_db_api formats underlying errors."""
    mock_discover = MagicMock(side_effect=BSMError("Base DB Broken"))
    monkeypatch.setattr(
        "bedrock_server_manager.api.player.discover_and_store_players", mock_discover
    )

    result = scan_and_update_player_db_api(app_context)

    assert result["status"] == "error"
    assert "Base DB Broken" in result["message"]


def test_scan_and_update_player_db_api_no_db(app_context, monkeypatch):
    """Test scan_and_update_player_db_api errors properly if no db initialized."""
    monkeypatch.setattr(type(app_context), "db", None)
    result = scan_and_update_player_db_api(app_context)
    assert result["status"] == "error"
    assert "not initialized" in result["message"]
