from pathlib import Path

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
from bedrock_server_manager.error import UserInputError


async def test_manual_players_persist_and_update_without_duplicates(app_context):
    response = await add_players_manually(
        AddPlayersManuallyRequest(player_strings=["Steve:1234", "Alex:5678"]),
        app_context=app_context,
    )
    assert response.count == 2
    await add_players_manually(
        AddPlayersManuallyRequest(player_strings=["Renamed:1234"]),
        app_context=app_context,
    )
    await app_context.reload()
    response = await get_all_known_players(
        GetAllKnownPlayersRequest(), app_context=app_context
    )
    assert {player.xuid: player.name for player in response.players} == {
        "1234": "Renamed",
        "5678": "Alex",
    }


async def test_log_scan_persists_real_player_entries(app_context, real_bedrock_server):
    Path(real_bedrock_server.paths.server_log_path).write_text(
        "[INFO] Player connected: Steve, xuid: 1234\n[INFO] Player connected: Alex, xuid: 5678\n"
    )
    response = await scan_and_update_player_db(
        ScanAndUpdatePlayerDbRequest(), app_context=app_context
    )
    assert response.details.scan_errors == []
    assert response.details.unique_players_submitted_for_saving == 2
    players = await get_all_known_players(
        GetAllKnownPlayersRequest(), app_context=app_context
    )
    assert {player.name for player in players.players} == {"Steve", "Alex"}


async def test_invalid_player_string_does_not_save_partial_input(app_context):
    with pytest.raises(UserInputError):
        await add_players_manually(
            AddPlayersManuallyRequest(player_strings=["Steve:1234", "invalid"]),
            app_context=app_context,
        )
    assert (
        await get_all_known_players(
            GetAllKnownPlayersRequest(), app_context=app_context
        )
    ).players == []


def test_empty_player_list_is_rejected():
    with pytest.raises(ValidationError):
        AddPlayersManuallyRequest(player_strings=[])
