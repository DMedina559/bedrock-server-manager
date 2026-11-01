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


async def test_player_api_manual_and_log_scan(app_context, real_bedrock_server):
    with pytest.raises(ValidationError):
        AddPlayersManuallyRequest(player_strings=[])

    # Invalid player string does not save partial input
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

    # Manual players persist and update without duplicates
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

    # Log scan persists real player entries
    Path(real_bedrock_server.paths.server_log_path).write_text(
        "[INFO] Player connected: Steve, xuid: 1234\n[INFO] Player connected:NewPlayer, xuid: 9999\n"
    )
    scan_resp = await scan_and_update_player_db(
        ScanAndUpdatePlayerDbRequest(), app_context=app_context
    )
    assert scan_resp.details.scan_errors == []
    assert scan_resp.details.unique_players_submitted_for_saving >= 1
    players = await get_all_known_players(
        GetAllKnownPlayersRequest(), app_context=app_context
    )
    assert "Steve" in {player.name for player in players.players}
