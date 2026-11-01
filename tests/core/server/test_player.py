import asyncio
import os


async def test_player_log_parsing_and_scanning(real_bedrock_server):
    """Test parsing log events, malformed lines, missing file, and incremental scanning."""
    server = real_bedrock_server

    # Missing file
    if os.path.exists(server.paths.server_log_path):
        os.remove(server.paths.server_log_path)
    assert await server.player_tracker.scan_log_for_players() == []

    # Parse connect/disconnect events
    lines = [
        "[2023-10-27 10:00:00] [INFO] Player connected: player1, xuid: 12345\n",
        "[2023-10-27 10:01:00] [INFO] Player connected: player2, xuid: 67890\n",
        "[2023-10-27 10:02:00] [INFO] Player disconnected: player1, xuid: 12345\n",
        "Some random log line\n",
        "[2023-10-27 10:03:00] [INFO] Player connected: player3, xuid: 11111\n",
        "[2023-10-27 10:04:00] [INFO] Player disconnected: player2, xuid: 67890\n",
    ]
    with open(server.paths.server_log_path, "w") as f:
        f.writelines(lines)

    valid_events = [
        e for e in server.player_tracker._parse_player_log_events() if e[0] is not None
    ]
    assert [e[:3] for e in valid_events] == [
        ("connect", "player1", "12345"),
        ("connect", "player2", "67890"),
        ("disconnect", "player1", "12345"),
        ("connect", "player3", "11111"),
        ("disconnect", "player2", "67890"),
    ]

    # Malformed lines
    with open(server.paths.server_log_path, "w") as f:
        f.writelines(
            [
                "[INFO] Player connected: player1, xuid: \n",
                "[INFO] Player connected: , xuid: 12345\n",
                "[INFO] Player connected: player1, xuid: 12345\n",
            ]
        )
    valid_events = [
        e for e in server.player_tracker._parse_player_log_events() if e[0] is not None
    ]
    assert [e[:3] for e in valid_events] == [("connect", "player1", "12345")]

    # Full scan and incremental scan
    server.player_tracker._last_log_offset = 0
    with open(server.paths.server_log_path, "w") as f:
        f.write("[INFO] Player connected: player1, xuid: 12345\n")

    players1 = await server.player_tracker.scan_log_for_players(incremental=True)
    assert len(players1) == 1 and players1[0]["name"] == "player1"

    with open(server.paths.server_log_path, "a") as f:
        f.write("[INFO] Player connected: player2, xuid: 67890\n")

    players2 = await server.player_tracker.scan_log_for_players(incremental=True)
    assert len(players2) == 1 and players2[0]["name"] == "player2"

    all_players = await server.player_tracker.scan_log_for_players(incremental=False)
    assert [p["name"] for p in all_players] == ["player1", "player2"]


async def test_update_online_players(real_bedrock_server):
    server = real_bedrock_server
    await server.start()
    await server.send_command("__DUMMY__ PLAYER_JOIN IntegrationPlayer")
    async with asyncio.timeout(5):
        while not await server.player_tracker.update_online_players():
            await asyncio.sleep(0.01)
    assert server.players == [{"name": "IntegrationPlayer", "xuid": "2535413537906883"}]
    await server.send_command("__DUMMY__ PLAYER_LEAVE IntegrationPlayer")
    async with asyncio.timeout(5):
        while await server.player_tracker.update_online_players():
            await asyncio.sleep(0.01)
    assert server.players == []
