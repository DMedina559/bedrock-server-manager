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


async def test_server_setting_http_write_notifies_other_connected_clients(
    admin_auth_client, real_bedrock_server, subscribed_socket
):
    import asyncio
    import json

    name = real_bedrock_server.server_name
    topic = "event:after_set_server_setting"
    async with subscribed_socket(topic) as browser, subscribed_socket(topic) as phone:
        response = await admin_auth_client.post(
            f"/api/server/{name}/settings/set",
            json={"key": "settings.target_version", "value": "LATEST"},
        )
        assert response.status_code == 200
        async with asyncio.timeout(5):
            first = json.loads(await browser.recv())
            second = json.loads(await phone.recv())
        assert first == second
        assert first["type"] == "event"
        assert first["topic"] == topic
        assert first["data"]["server_name"] == name
        assert first["data"]["key"] == "settings.target_version"
        assert first["data"]["value"] == "LATEST"
        assert first["data"]["result"]["status"] == "success"
        assert first["revision"] > 0
        assert first["epoch"]
        settings = (
            await admin_auth_client.get(f"/api/server/{name}/settings/get")
        ).json()
        assert settings["settings"]["settings"]["target_version"] == "LATEST"
