import asyncio
import json

from bedrock_server_manager.state.app_state import AppState


async def test_server_settings_round_trip_roles_and_websocket_notifications(
    auth_client,
    admin_auth_client,
    real_bedrock_server,
    app_context,
    subscribed_socket,
):
    name = real_bedrock_server.server_name
    base = f"/api/server/{name}/settings"

    # User can read but not change server settings
    assert (await auth_client.get(base + "/get")).status_code == 200
    assert (
        await auth_client.post(
            base + "/set", json={"key": "settings.autoupdate", "value": True}
        )
    ).status_code == 403

    # Invalid server setting preserves state
    original = await real_bedrock_server.get_autoupdate()
    for payload in (
        {"key": "settings.autoupdate", "value": "invalid"},
        {"key": "", "value": True},
    ):
        response = await admin_auth_client.post(base + "/set", json=payload)
        assert response.status_code in {400, 422}
        assert await real_bedrock_server.get_autoupdate() == original

    # Valid round trip survives reload
    response = await admin_auth_client.post(
        base + "/set", json={"key": "settings.autoupdate", "value": True}
    )
    assert response.status_code == 200
    assert (await admin_auth_client.get(base + "/get")).json()["settings"]["settings"][
        "autoupdate"
    ] is True

    restored = AppState()
    await app_context.storage.load_state(restored)
    assert restored.servers.get(name).autoupdate is True

    # HTTP write notifies connected websocket clients
    topic = "event:after_set_server_setting"
    async with subscribed_socket(topic) as browser, subscribed_socket(topic) as phone:
        response = await admin_auth_client.post(
            base + "/set",
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
        settings = (await admin_auth_client.get(base + "/get")).json()
        assert settings["settings"]["settings"]["target_version"] == "LATEST"
