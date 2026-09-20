def test_parse_player_log_events(real_bedrock_server):
    """Test parsing log lines for player connect and disconnect events."""
    server = real_bedrock_server

    # Mock is_running to return True so update_online_players doesn\'t clear the list

    lines = [
        "[2023-10-27 10:00:00] [INFO] Player connected: player1, xuid: 12345\n",
        "[2023-10-27 10:01:00] [INFO] Player connected: player2, xuid: 67890\n",
        "[2023-10-27 10:02:00] [INFO] Player disconnected: player1, xuid: 12345\n",
        "Some random log line\n",
        "[2023-10-27 10:03:00] [INFO] Player connected: player3, xuid: 11111\n",
        "[2023-10-27 10:04:00] [INFO] Player disconnected: player2, xuid: 67890\n",
    ]
    with open(server.server_log_path, "w") as f:
        f.writelines(lines)

    events = list(server._parse_player_log_events())

    valid_events = [e for e in events if e[0] is not None]
    assert len(valid_events) == 5  # 3 connect, 2 disconnect
    assert valid_events[0][:3] == ("connect", "player1", "12345")
    assert valid_events[1][:3] == ("connect", "player2", "67890")
    assert valid_events[2][:3] == ("disconnect", "player1", "12345")
    assert valid_events[3][:3] == ("connect", "player3", "11111")
    assert valid_events[4][:3] == ("disconnect", "player2", "67890")


def test_parse_player_log_events_malformed(real_bedrock_server):
    """Test parsing log lines with malformed output."""
    server = real_bedrock_server

    # Mock is_running to return True so update_online_players doesn\'t clear the list

    lines = [
        "[INFO] Player connected: player1, xuid: \n",
        "[INFO] Player connected: , xuid: 12345\n",
        "[INFO] Player connected: player1, xuid: 12345\n",
    ]
    with open(server.server_log_path, "w") as f:
        f.writelines(lines)

    events = list(server._parse_player_log_events())
    valid_events = [e for e in events if e[0] is not None]
    assert len(valid_events) == 1
    assert valid_events[0][:3] == ("connect", "player1", "12345")


async def test_scan_log_for_players(real_bedrock_server):
    """Test scanning the log file for players."""
    server = real_bedrock_server

    # Mock is_running to return True so update_online_players doesn\'t clear the list

    with open(server.server_log_path, "w") as f:
        f.write("[INFO] Player connected: player1, xuid: 12345\n")
        f.write("[INFO] Player connected: player2, xuid: 67890\n")
        f.write("[INFO] Player disconnected: player1, xuid: 12345\n")

    players = await server.scan_log_for_players()

    assert len(players) == 2
    assert players[0]["name"] == "player1"
    assert players[1]["name"] == "player2"


async def test_scan_log_for_players_incremental(real_bedrock_server):
    """Test scanning the log file incrementally avoids reading old lines."""
    server = real_bedrock_server

    # Mock is_running to return True so update_online_players doesn\'t clear the list

    with open(server.server_log_path, "w") as f:
        f.write("[INFO] Player connected: player1, xuid: 12345\n")

    players1 = await server.scan_log_for_players(incremental=True)
    assert len(players1) == 1

    with open(server.server_log_path, "a") as f:
        f.write("[INFO] Player connected: player2, xuid: 67890\n")

    players2 = await server.scan_log_for_players(incremental=True)
    assert len(players2) == 1  # Only player2 picked up this time
    assert players2[0]["name"] == "player2"


async def test_scan_log_for_players_missing_file(real_bedrock_server):
    """Test scanning returns empty list if log file is missing."""
    server = real_bedrock_server

    # Mock is_running to return True so update_online_players doesn\'t clear the list
    import os

    if os.path.exists(server.server_log_path):
        os.remove(server.server_log_path)

    players = await server.scan_log_for_players()
    assert players == []


async def test_update_online_players(real_bedrock_server):
    from unittest.mock import AsyncMock

    real_bedrock_server.is_running = AsyncMock(return_value=True)
    real_bedrock_server.is_running = AsyncMock(return_value=True)
    """Test updating the online players property from the log."""
    server = real_bedrock_server

    # Mock is_running to return True so update_online_players doesn\'t clear the list

    with open(server.server_log_path, "w") as f:
        f.write("[INFO] Player connected: player1, xuid: 12345\n")

    players = await server.update_online_players()
    # Let us check what is in the players log before asserting
    print("PLAYERS:", players)
    assert len(players) == 1
    assert players[0]["name"] == "player1"
    assert getattr(server, "players", []) == players
