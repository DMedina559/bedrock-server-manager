import asyncio
import json


async def test_http_lifecycle_summary_roles_and_oracle_prevention(
    unauth_client, auth_client, admin_auth_client, real_bedrock_server
):
    name = real_bedrock_server.server_name
    base = f"/api/server/{name}"

    # Summary and missing server
    summary = await admin_auth_client.get(base + "/summary")
    assert summary.status_code == 200 and summary.json()["name"] == name
    assert (
        await admin_auth_client.post("/api/server/missing/start")
    ).status_code == 404

    # Blocked command
    assert (
        await admin_auth_client.post(base + "/send_command", json={"command": "stop"})
    ).status_code == 403

    # Role enforcement and server existence oracle prevention
    for target in (name, "definitely_nonexistent_server"):
        assert (
            await unauth_client.get(f"/api/server/{target}/summary")
        ).status_code == 401
        for action in ("start", "stop", "restart", "send_command"):
            payload = {"command": "list"} if action == "send_command" else {}
            assert (
                await unauth_client.post(f"/api/server/{target}/{action}", json=payload)
            ).status_code == 401
            assert (
                await auth_client.post(f"/api/server/{target}/{action}", json=payload)
            ).status_code == 403
    assert not await real_bedrock_server.is_running()

    # Lifecycle controls real server
    response = await admin_auth_client.post(base + "/start")
    assert response.status_code == 200 and response.json()["outcome"] == "started"
    first_pid = real_bedrock_server.process._process.pid
    assert (await admin_auth_client.post(base + "/start")).json()[
        "outcome"
    ] == "already_running"
    assert real_bedrock_server.process._process.pid == first_pid

    cmd_resp = await admin_auth_client.post(
        base + "/send_command", json={"command": "__DUMMY__ PLAYER_JOIN HTTPPlayer"}
    )
    assert cmd_resp.status_code == 200

    restart_resp = await admin_auth_client.post(
        base + "/restart", json={"send_message": False}
    )
    assert restart_resp.status_code == 200
    assert real_bedrock_server.process._process.pid != first_pid

    assert (await admin_auth_client.post(base + "/stop")).json()["outcome"] == "stopped"
    assert not await real_bedrock_server.is_running()
    assert (await admin_auth_client.post(base + "/stop")).json()[
        "outcome"
    ] == "already_stopped"


async def test_dummy_player_events_and_delete_task(
    admin_auth_client,
    app_context,
    real_bedrock_server,
    subscribed_socket,
    wait_for_task,
):
    server = real_bedrock_server
    name = server.server_name
    await app_context.settings.set("monitoring.process_interval_sec", 1)
    await app_context.settings.set("monitoring.player_interval_sec", 1)
    base = f"/api/server/{name}"
    assert (await admin_auth_client.post(base + "/start")).status_code == 200
    manager = app_context.bedrock_process_manager
    manager.monitoring_task.cancel()
    await asyncio.gather(manager.monitoring_task, return_exceptions=True)
    await manager.start()
    try:
        async with subscribed_socket("event:after_server_players_change") as socket:
            for command, expected_count in [("PLAYER_JOIN", 1), ("PLAYER_LEAVE", 0)]:
                response = await admin_auth_client.post(
                    base + "/send_command",
                    json={"command": f"__DUMMY__ {command} IntegrationPlayer"},
                )
                assert response.status_code == 200
                async with asyncio.timeout(10):
                    message = json.loads(await socket.recv())
                assert message["topic"] == "event:after_server_players_change"
                result = message["data"]["result"]
                assert result["server_name"] == name
                assert result["player_count"] == expected_count
                expected_players = (
                    [{"name": "IntegrationPlayer", "xuid": "2535413537906883"}]
                    if expected_count
                    else []
                )
                assert result["players"] == expected_players
                assert server.players == expected_players
                assert server.player_count == expected_count
    finally:
        await manager.quiesce()
        await server.stop()

    # Delete task retains server identity
    del_resp = await admin_auth_client.delete(f"/api/server/{name}/delete")
    assert del_resp.status_code == 202
    task = await wait_for_task(app_context, del_resp.json()["task_id"])
    assert task.status == "completed"
    assert task.result["server_name"] == name
    assert task.result["status"] == "success"
    assert name not in app_context._servers
