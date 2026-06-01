import os

import pytest

from bedrock_server_manager.core.player import (
    discover_and_store_players,
    get_known_players,
    parse_player_string,
    save_player_data,
)
from bedrock_server_manager.error import AppFileNotFoundError, UserInputError


@pytest.mark.parametrize(
    "input_str, raises_error, match_msg",
    [
        ("ValidName:123", False, None),
        (" Valid : 123 ", False, None),
        ("NameOnly", True, "Invalid player data format: 'NameOnly'."),
        (":", True, "Name and XUID cannot be empty in ':'."),
        ("Name:", True, "Name and XUID cannot be empty in 'Name:'."),
        (":123", True, "Name and XUID cannot be empty in ':123'."),
        ("", False, None),
        (None, False, None),
        ("Valid:1,Invalid,Valid2:2", True, "Invalid player data format: 'Invalid'."),
    ],
)
def test_parse_player_string(input_str, raises_error, match_msg):
    if raises_error:
        with pytest.raises(UserInputError, match=match_msg):
            parse_player_string(input_str)
    else:
        result = parse_player_string(input_str)
        if input_str and input_str.strip():
            assert len(result) > 0
        else:
            assert result == []


def test_save_player_data_new_db(app_context):
    db_manager = app_context.manager.settings.db.session_manager
    players_to_save = [
        {"name": "Gamer", "xuid": "100"},
        {"name": "Admin", "xuid": "007"},
    ]

    saved_count = save_player_data(db_manager(), players_to_save)
    assert saved_count == 2

    players = get_known_players(db_manager())
    assert len(players) == 2
    assert {"name": "Gamer", "xuid": "100"} in players
    assert {"name": "Admin", "xuid": "007"} in players


def test_save_player_data_update_existing_db(app_context):
    db_manager = app_context.manager.settings.db.session_manager
    save_player_data(db_manager(), [{"name": "ToUpdate", "xuid": "222"}])

    players_to_save = [
        {"name": "NewPlayer", "xuid": "333"},
        {"name": "UpdatedName", "xuid": "222"},
    ]
    saved_count = save_player_data(db_manager(), players_to_save)
    assert saved_count == 2

    players = get_known_players(db_manager())
    assert len(players) == 2
    assert {"name": "NewPlayer", "xuid": "333"} in players
    assert {"name": "UpdatedName", "xuid": "222"} in players


def test_save_player_data_invalid_input(app_context):
    db_manager = app_context.manager.settings.db.session_manager
    with pytest.raises(UserInputError, match="players_data must be a list."):
        save_player_data(db_manager(), {"name": "A", "xuid": "1"})

    with pytest.raises(UserInputError, match="Invalid player entry format"):
        save_player_data(db_manager(), [{"name": "A"}])

    with pytest.raises(UserInputError, match="Invalid player entry format"):
        save_player_data(db_manager(), [{"name": "", "xuid": "1"}])


def test_get_known_players(app_context):
    db_manager = app_context.manager.settings.db.session_manager
    players_to_save = [
        {"name": "PlayerX", "xuid": "789"},
        {"name": "PlayerY", "xuid": "123"},
    ]
    save_player_data(db_manager(), players_to_save)

    players = get_known_players(db_manager())
    assert len(players) == 2
    assert {"name": "PlayerX", "xuid": "789"} in players
    assert {"name": "PlayerY", "xuid": "123"} in players


def test_get_known_players_empty_db(app_context):
    db_manager = app_context.manager.settings.db.session_manager
    players = get_known_players(db_manager())
    assert players == []


def test_discover_and_store_players_from_all_server_logs(app_context, mocker):
    server = app_context.get_server("test_server")
    log_file_path = os.path.join(server.server_dir, "server_output.txt")
    with open(log_file_path, "w") as f:
        f.write("Player connected: Alpha, xuid: 1\n")
        f.write("Player connected: Beta, xuid: 2\n")

    mocker.patch(
        "bedrock_server_manager.core.bedrock_server.BedrockServer.scan_log_for_players",
        return_value=[
            {"name": "Alpha", "xuid": "1"},
            {"name": "Beta", "xuid": "2"},
        ],
    )
    db_manager = app_context.manager.settings.db.session_manager
    results = discover_and_store_players(
        app_context.manager._base_dir, app_context, db_manager()
    )

    assert results["total_entries_in_logs"] == 2
    assert results["unique_players_submitted_for_saving"] == 2
    assert results["actually_saved_or_updated_in_db"] == 2
    assert len(results["scan_errors"]) == 0

    players = get_known_players(db_manager())
    assert len(players) == 2
    assert {"name": "Alpha", "xuid": "1"} in players
    assert {"name": "Beta", "xuid": "2"} in players


def test_discover_players_base_dir_not_exist(app_context, mocker):
    base_dir = "/path/to/non_existent_base"
    db_manager = app_context.manager.settings.db.session_manager
    mocker.patch("os.path.isdir", return_value=False)

    with pytest.raises(AppFileNotFoundError, match="Server base directory"):
        discover_and_store_players(base_dir, app_context, db_manager())
