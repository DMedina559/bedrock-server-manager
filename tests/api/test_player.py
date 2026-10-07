from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from bedrock_server_manager.api.models import (
    AddPlayersManuallyRequest,
    GetAllKnownPlayersRequest,
    ScanAndUpdatePlayerDbRequest,
)
from bedrock_server_manager.api.player import (
    add_players_manually,
    get_all_known_players,
    scan_and_update_player_db,
)
from bedrock_server_manager.error import BSMError, UserInputError


async def test_add_players_manually_success(app_context, monkeypatch):
    """Test add_players_manually parses input lists and routes saves."""
    mock_save = AsyncMock()
    monkeypatch.setattr("bedrock_server_manager.api.player.save_player_data", mock_save)

    result = (
        await add_players_manually(
            request=AddPlayersManuallyRequest(
                player_strings=["user1:1234", "user2:5678"]
            ),
            app_context=app_context,
        )
    ).model_dump(mode="python")

    assert result["status"] == "success"
    assert result["count"] == 2
    mock_save.assert_called_once()


async def test_add_players_manually_invalid_input(app_context):
    """Test add_players_manually catches bad inputs directly."""
    with pytest.raises(ValidationError):
        (
            await add_players_manually(
                request=AddPlayersManuallyRequest(player_strings=[]),
                app_context=app_context,
            )
        ).model_dump(mode="python")


async def test_add_players_manually_parse_error(app_context, monkeypatch):
    """Test add_players_manually catches UserInputError from the parse_player_string core util."""

    def mock_parse(*args):
        raise UserInputError("Bad formatting")

    monkeypatch.setattr(
        "bedrock_server_manager.api.player.parse_player_string", mock_parse
    )

    with pytest.raises(UserInputError):
        (
            await add_players_manually(
                request=AddPlayersManuallyRequest(player_strings=["bad_format"]),
                app_context=app_context,
            )
        ).model_dump(mode="python")


async def test_add_players_manually_no_db(app_context, monkeypatch):
    """Test add_players_manually errors properly if no db initialized."""
    # We must patch the underlying hidden variable accessed by the property getter
    monkeypatch.setattr(type(app_context), "storage", None)
    with pytest.raises(BSMError):
        (
            await add_players_manually(
                request=AddPlayersManuallyRequest(player_strings=["player1:123"]),
                app_context=app_context,
            )
        ).model_dump(mode="python")


async def test_get_all_known_players_success(app_context, monkeypatch):
    """Test get_all_known_players loads generic players array via mock."""
    mock_get = AsyncMock(
        return_value=[{"name": "p1", "xuid": "1"}, {"name": "p2", "xuid": "2"}]
    )
    monkeypatch.setattr("bedrock_server_manager.api.player.get_known_players", mock_get)

    result = (
        await get_all_known_players(
            request=GetAllKnownPlayersRequest(), app_context=app_context
        )
    ).model_dump(mode="python")

    assert result["status"] == "success"
    assert len(result["players"]) == 2


async def test_get_all_known_players_no_db(app_context, monkeypatch):
    """Test get_all_known_players errors properly if no db initialized."""
    monkeypatch.setattr(type(app_context), "storage", None)
    with pytest.raises(BSMError):
        (
            await get_all_known_players(
                request=GetAllKnownPlayersRequest(), app_context=app_context
            )
        ).model_dump(mode="python")


async def test_scan_and_update_player_db_success(app_context, monkeypatch):
    """Test scan_and_update_player_db delegates correctly generating complex stats mapping."""
    mock_discover = AsyncMock(
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

    result = (
        await scan_and_update_player_db(
            request=ScanAndUpdatePlayerDbRequest(), app_context=app_context
        )
    ).model_dump(mode="python")

    assert result["status"] == "success"
    assert result["details"]["actually_saved_or_updated_in_db"] == 1
    assert "actually saved/updated" in result["message"].lower()


async def test_scan_and_update_player_db_bsm_error(app_context, monkeypatch):
    """Test scan_and_update_player_db formats underlying errors."""
    mock_discover = AsyncMock(side_effect=BSMError("Base DB Broken"))
    monkeypatch.setattr(
        "bedrock_server_manager.api.player.discover_and_store_players", mock_discover
    )

    with pytest.raises(BSMError):
        (
            await scan_and_update_player_db(
                request=ScanAndUpdatePlayerDbRequest(), app_context=app_context
            )
        ).model_dump(mode="python")


async def test_scan_and_update_player_db_no_db(app_context, monkeypatch):
    """Test scan_and_update_player_db errors properly if no db initialized."""
    monkeypatch.setattr(type(app_context), "storage", None)
    with pytest.raises(BSMError):
        (
            await scan_and_update_player_db(
                request=ScanAndUpdatePlayerDbRequest(), app_context=app_context
            )
        ).model_dump(mode="python")
