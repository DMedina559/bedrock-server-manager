import pytest


async def test_ban_round_trip_persists_database(
    admin_auth_client, real_bedrock_server, app_context
):
    base = f"/api/server/{real_bedrock_server.server_name}/bans"
    response = await admin_auth_client.post(
        base + "/add",
        json={"player_name": "BadPlayer", "xuid": "12345", "reason": "Testing"},
    )
    assert response.status_code == 200
    bans = (await admin_auth_client.get(base + "/get")).json()["bans"]
    assert any(ban["xuid"] == "12345" and ban["reason"] == "Testing" for ban in bans)
    await app_context.reload()
    assert any(
        ban["xuid"] == "12345"
        for ban in (await admin_auth_client.get(base + "/get")).json()["bans"]
    )
    response = await admin_auth_client.request(
        "DELETE", base + "/remove", json={"xuid": "12345"}
    )
    assert response.status_code == 200
    assert not (await admin_auth_client.get(base + "/get")).json()["bans"]


@pytest.mark.parametrize("authenticated,expected", [(False, 401), (True, 403)])
async def test_bans_require_admin(
    unauth_client, auth_client, real_bedrock_server, authenticated, expected
):
    client = auth_client if authenticated else unauth_client
    assert (
        await client.get(f"/api/server/{real_bedrock_server.server_name}/bans/get")
    ).status_code == expected


async def test_invalid_ban_does_not_write_database(
    admin_auth_client, real_bedrock_server
):
    base = f"/api/server/{real_bedrock_server.server_name}/bans"
    response = await admin_auth_client.post(
        base + "/add", json={"player_name": "BadPlayer", "xuid": ""}
    )
    assert response.status_code == 422
    assert not (await admin_auth_client.get(base + "/get")).json()["bans"]
