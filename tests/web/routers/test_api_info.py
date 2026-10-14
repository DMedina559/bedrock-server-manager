from pathlib import Path


async def test_server_status_and_listing_follow_real_process(
    auth_client, real_bedrock_server
):
    base = f"/api/server/{real_bedrock_server.server_name}"
    assert (await auth_client.get(base + "/validate")).status_code == 200
    assert (await auth_client.get(base + "/status")).json()["running"] is False
    await real_bedrock_server.start()
    assert (await auth_client.get(base + "/status")).json()["running"] is True
    response = await auth_client.get("/api/servers")
    assert response.status_code == 200
    assert response.json()["servers"][0]["name"] == real_bedrock_server.server_name
    await real_bedrock_server.stop()
    assert (await auth_client.get(base + "/status")).json()["running"] is False


async def test_player_endpoints_use_persistent_database(
    admin_auth_client, app_context, real_bedrock_server
):
    response = await admin_auth_client.post(
        "/api/players/add", json={"players": ["Steve:1234"]}
    )
    assert response.status_code == 200
    assert response.json()["count"] == 1
    Path(real_bedrock_server.paths.server_log_path).write_text(
        "[INFO] Player connected: Alex, xuid: 5678\n"
    )
    assert (await admin_auth_client.put("/api/players/scan")).status_code == 200
    await app_context.reload()
    response = await admin_auth_client.get("/api/players/get")
    assert response.status_code == 200
    assert {player["name"] for player in response.json()["players"]} == {
        "Steve",
        "Alex",
    }


async def test_system_info_and_real_custom_themes(unauth_client, app_context, tmp_path):
    response = await unauth_client.get("/api/info")
    assert response.status_code == 200
    assert response.json()["info"]["app_version"]
    themes = tmp_path / "themes"
    themes.mkdir()
    (themes / "integration.css").write_text("body {}")
    await app_context.settings.set("paths.themes", str(themes))
    response = await unauth_client.get("/api/info/themes")
    assert response.status_code == 200
    assert response.json()["themes"][0] == "default"
    assert "integration" in response.json()["themes"]


async def test_information_endpoints_enforce_roles(unauth_client, auth_client):
    assert (await unauth_client.get("/api/servers")).status_code == 401
    assert (
        await auth_client.post("/api/players/add", json={"players": ["Steve:1234"]})
    ).status_code == 403


async def test_unknown_server_validation(auth_client):
    assert (await auth_client.get("/api/server/missing/validate")).status_code == 404
