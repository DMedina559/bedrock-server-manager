"""Administrative event inspection through the actual HTTP contract."""

import pytest


async def test_catalog_and_activity_are_admin_only(
    admin_auth_client, auth_client, unauth_client, app_context
):
    for path in ("/api/events", "/api/events/activity"):
        assert (await unauth_client.get(path)).status_code == 401
        assert (await auth_client.get(path)).status_code == 403
    catalog = await admin_auth_client.get("/api/events")
    assert catalog.status_code == 200
    names = {definition["name"] for definition in catalog.json()["events"]}
    assert "after_server_players_change" in names
    assert "before_server_status_change" in names
    await app_context.events.emit("example:changed", {"value": "private-history-value"})
    activity = await admin_auth_client.get("/api/events/activity")
    assert activity.status_code == 200
    assert activity.json()["recent"][-1]["name"] == "example:changed"
    assert "private-history-value" not in activity.text


@pytest.mark.parametrize(
    "event_name",
    ["before_server_start", "before_server_status_change", "on_manager_startup"],
)
async def test_external_trigger_cannot_forge_core_hooks(admin_auth_client, event_name):
    response = await admin_auth_client.post(
        "/api/plugins/trigger_event",
        json={"event_name": event_name, "payload": {}},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"
