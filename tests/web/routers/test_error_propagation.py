"""Exercise domain failures through authenticated routes and real plugins."""

import pytest


@pytest.mark.parametrize(
    "suffix,payload,event_name",
    [
        ("allowlist/add", {"players": ["Steve"]}, "before_allowlist_change"),
        (
            "properties/set",
            {"properties": {"server-name": "Changed"}},
            "before_properties_change",
        ),
        (
            "settings/set",
            {"key": "settings.autoupdate", "value": True},
            "before_set_server_setting",
        ),
        (
            "permissions/set",
            {
                "permissions": [
                    {"xuid": "123", "name": "Steve", "permission_level": "operator"}
                ]
            },
            "before_permission_change",
        ),
        ("send_command", {"command": "list"}, "before_command_send"),
    ],
)
async def test_plugin_cancellation_preserves_conflict_response(
    admin_auth_client, real_bedrock_server, plugin_factory, suffix, payload, event_name
):
    plugin = await plugin_factory(
        "cancel_operations",
        "from bedrock_server_manager import PluginBase\nclass Observer(PluginBase):\n    version = '1.0'\n",
    )

    async def cancel(event, **kwargs):
        event.cancel("private plugin reason")

    plugin.api.listen_for_event(event_name, cancel)
    response = await admin_auth_client.post(
        f"/api/server/{real_bedrock_server.server_name}/{suffix}", json=payload
    )
    assert response.status_code == 409
    assert "private plugin reason" not in response.text
    if suffix == "permissions/set":
        assert response.json()["error"]["details"]["updated"] == 0
    else:
        assert response.json()["error"]["code"] == "operation_canceled"


async def test_command_domain_failures_keep_http_classification(
    admin_auth_client, real_bedrock_server
):
    path = f"/api/server/{real_bedrock_server.server_name}/send_command"
    blocked = await admin_auth_client.post(path, json={"command": "stop"})
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "forbidden"
    stopped = await admin_auth_client.post(path, json={"command": "list"})
    assert stopped.status_code == 409
    assert stopped.json()["error"]["code"] == "conflict"
