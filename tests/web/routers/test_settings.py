async def test_global_settings_round_trip_validation_and_roles(
    unauth_client, auth_client, admin_auth_client, app_context
):
    assert (await unauth_client.get("/api/settings/get")).status_code == 401
    assert (await auth_client.get("/api/settings/get")).status_code == 403

    response = await admin_auth_client.post(
        "/api/settings/set", json={"key": "retention.downloads", "value": 7}
    )
    assert response.status_code == 200
    assert app_context.settings.get("retention.downloads") == 7
    assert (await admin_auth_client.get("/api/settings/get")).json()["settings"][
        "retention"
    ]["downloads"] == 7
    assert (await admin_auth_client.put("/api/settings/reload")).status_code == 200
    assert app_context.settings.get("retention.downloads") == 7

    for payload in (
        {"key": "retention.downloads", "value": -1},
        {"key": "retention.downloads", "value": "invalid"},
        {"key": "", "value": 1},
    ):
        response = await admin_auth_client.post("/api/settings/set", json=payload)
        assert response.status_code in {400, 422}
        assert app_context.settings.get("retention.downloads") == 7
    await app_context.settings.reload()
    assert app_context.settings.get("retention.downloads") == 7
