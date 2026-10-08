import pytest


async def test_http_lifecycle_controls_real_server(
    admin_auth_client, real_bedrock_server
):
    base = f"/api/server/{real_bedrock_server.server_name}"
    response = await admin_auth_client.post(base + "/start")
    assert response.status_code == 200
    assert response.json()["outcome"] == "started"
    first_pid = real_bedrock_server._process.pid
    assert (await admin_auth_client.post(base + "/start")).json()[
        "outcome"
    ] == "already_running"
    assert real_bedrock_server._process.pid == first_pid
    response = await admin_auth_client.post(
        base + "/send_command", json={"command": "__DUMMY__ PLAYER_JOIN HTTPPlayer"}
    )
    assert response.status_code == 200
    response = await admin_auth_client.post(
        base + "/restart", json={"send_message": False}
    )
    assert response.status_code == 200
    assert real_bedrock_server._process.pid != first_pid
    assert (await admin_auth_client.post(base + "/stop")).json()["outcome"] == "stopped"
    assert not await real_bedrock_server.is_running()
    assert (await admin_auth_client.post(base + "/stop")).json()[
        "outcome"
    ] == "already_stopped"


async def test_summary_matches_actual_server(admin_auth_client, real_bedrock_server):
    response = await admin_auth_client.get(
        f"/api/server/{real_bedrock_server.server_name}/summary"
    )
    assert response.status_code == 200
    assert response.json()["name"] == real_bedrock_server.server_name


@pytest.mark.parametrize("action", ["start", "stop", "restart", "send_command"])
@pytest.mark.parametrize("authenticated,expected", [(False, 401), (True, 403)])
async def test_server_actions_enforce_roles(
    unauth_client, auth_client, real_bedrock_server, action, authenticated, expected
):
    client = auth_client if authenticated else unauth_client
    response = await client.post(
        f"/api/server/{real_bedrock_server.server_name}/{action}",
        json={"command": "list"} if action == "send_command" else {},
    )
    assert response.status_code == expected
    assert not await real_bedrock_server.is_running()


async def test_http_blocked_command_is_rejected(admin_auth_client, real_bedrock_server):
    response = await admin_auth_client.post(
        f"/api/server/{real_bedrock_server.server_name}/send_command",
        json={"command": "stop"},
    )
    assert response.status_code == 403


async def test_missing_server_is_not_found(admin_auth_client):
    assert (
        await admin_auth_client.post("/api/server/missing/start")
    ).status_code == 404
