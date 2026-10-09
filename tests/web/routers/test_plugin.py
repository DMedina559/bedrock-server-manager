import pytest


async def test_http_plugin_lifecycle_persists_configuration(
    admin_auth_client, app_context, plugin_factory
):
    plugin = await plugin_factory(
        "integration",
        "from bedrock_server_manager import PluginBase\nclass Integration(PluginBase):\n    version = '1.0'\n",
    )
    response = await admin_auth_client.get("/api/plugins")
    assert response.status_code == 200
    assert response.json()["plugins"]["integration"]["enabled"] is True
    response = await admin_auth_client.post(
        "/api/plugins/integration", json={"enabled": False}
    )
    assert response.status_code == 200
    assert not any(
        item.api._plugin_name == "integration"
        for item in app_context.plugin_manager.plugins
    )
    await app_context.plugin_manager._synchronize_config_with_disk()
    assert app_context.plugin_manager.plugin_config["integration"]["enabled"] is False
    response = await admin_auth_client.post(
        "/api/plugins/integration", json={"enabled": True}
    )
    assert response.status_code == 200
    assert (
        next(
            item
            for item in app_context.plugin_manager.plugins
            if item.api._plugin_name == "integration"
        )
        is not plugin
    )
    previous = next(
        item
        for item in app_context.plugin_manager.plugins
        if item.api._plugin_name == "integration"
    )
    response = await admin_auth_client.post("/api/plugins/integration/reload")
    assert response.status_code == 200
    assert (
        next(
            item
            for item in app_context.plugin_manager.plugins
            if item.api._plugin_name == "integration"
        )
        is not previous
    )
    assert (await admin_auth_client.put("/api/plugins/reload")).status_code == 200
    assert any(
        item.api._plugin_name == "integration"
        for item in app_context.plugin_manager.plugins
    )


async def test_http_external_event_reaches_real_plugin(
    admin_auth_client, plugin_factory
):
    plugin = await plugin_factory(
        "events",
        "from bedrock_server_manager import PluginBase\nclass Events(PluginBase):\n    version = '1.0'\n",
    )
    received = []

    async def listener(*args, **kwargs):
        received.append((args, kwargs))

    plugin.api.listen_for_event("integration_event", listener)
    response = await admin_auth_client.post(
        "/api/plugins/trigger_event",
        json={"event_name": "integration_event", "payload": {"value": 7}},
    )
    assert response.status_code == 200
    assert len(received) == 1
    assert received[0][1]["value"] == 7


@pytest.mark.parametrize(
    "client_name,code", [("unauth_client", 401), ("auth_client", 403)]
)
async def test_plugin_management_requires_admin(
    unauth_client, auth_client, client_name, code
):
    client = {"unauth_client": unauth_client, "auth_client": auth_client}[client_name]
    assert (await client.get("/api/plugins")).status_code == code


async def test_unknown_plugin_is_rejected(admin_auth_client):
    assert (
        await admin_auth_client.post("/api/plugins/missing", json={"enabled": True})
    ).status_code == 400
