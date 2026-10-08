import pytest


async def test_server_settings_round_trip_survives_reload(
    admin_auth_client, real_bedrock_server, app_context
):
    base = f"/api/server/{real_bedrock_server.server_name}/settings"
    response = await admin_auth_client.post(
        base + "/set", json={"key": "settings.autoupdate", "value": True}
    )
    assert response.status_code == 200
    assert (await admin_auth_client.get(base + "/get")).json()["settings"]["settings"][
        "autoupdate"
    ] is True
    from bedrock_server_manager.state.app_state import AppState

    restored = AppState()
    await app_context.storage.load_state(restored)
    assert restored.servers.get(real_bedrock_server.server_name).autoupdate is True


async def test_user_can_read_but_not_change_server_settings(
    auth_client, real_bedrock_server
):
    base = f"/api/server/{real_bedrock_server.server_name}/settings"
    assert (await auth_client.get(base + "/get")).status_code == 200
    assert (
        await auth_client.post(
            base + "/set", json={"key": "settings.autoupdate", "value": True}
        )
    ).status_code == 403


@pytest.mark.parametrize(
    "payload",
    [{"key": "settings.autoupdate", "value": "invalid"}, {"key": "", "value": True}],
)
async def test_invalid_server_setting_preserves_state(
    admin_auth_client, real_bedrock_server, payload
):
    original = await real_bedrock_server.get_autoupdate()
    response = await admin_auth_client.post(
        f"/api/server/{real_bedrock_server.server_name}/settings/set", json=payload
    )
    assert response.status_code in {400, 422}
    assert await real_bedrock_server.get_autoupdate() == original
