import pytest


async def test_global_settings_round_trip_survives_reload(
    admin_auth_client, app_context
):
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


@pytest.mark.parametrize(
    "payload",
    [
        {"key": "retention.downloads", "value": -1},
        {"key": "retention.downloads", "value": "invalid"},
        {"key": "", "value": 1},
    ],
)
async def test_invalid_setting_preserves_persisted_value(
    admin_auth_client, app_context, payload
):
    original = app_context.settings.get("retention.downloads")
    response = await admin_auth_client.post("/api/settings/set", json=payload)
    assert response.status_code in {400, 422}
    assert app_context.settings.get("retention.downloads") == original
    await app_context.settings.reload()
    assert app_context.settings.get("retention.downloads") == original


@pytest.mark.parametrize("authenticated,expected", [(False, 401), (True, 403)])
async def test_global_settings_require_admin(
    unauth_client, auth_client, authenticated, expected
):
    client = auth_client if authenticated else unauth_client
    assert (await client.get("/api/settings/get")).status_code == expected
