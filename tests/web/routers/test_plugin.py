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


async def test_typed_plugin_settings_are_validated_and_persisted(
    admin_auth_client, unauth_client, app_context, tmp_path
):
    from sqlalchemy import select
    from bedrock_server_manager.db.models import PluginSetting
    from bedrock_server_manager.error import UserInputError
    import pytest

    (tmp_path / "plugins" / "typed_settings.py").write_text(
        """from pydantic import BaseModel, ConfigDict, Field, SecretStr
from bedrock_server_manager import PluginBase
class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    count: int = Field(default=3, ge=1, le=10, description="How many attempts")
    enabled: bool = True
    token: SecretStr = SecretStr("initial")
class TypedPlugin(PluginBase):
    version = "1.0"
    settings_model = Settings
"""
    )
    listed = (await admin_auth_client.get("/api/plugins")).json()
    assert listed["plugins"]["typed_settings"]["has_settings"] is True
    path = "/api/plugins/typed_settings/settings"
    assert (await unauth_client.get(path)).status_code == 401
    response = await admin_auth_client.get(path)
    assert response.status_code == 200
    data = response.json()
    assert data["settings"] == {"count": 3, "enabled": True, "token": "initial"}
    assert data["settings_schema"]["properties"]["count"]["maximum"] == 10
    assert (
        await admin_auth_client.put(
            path, json={"settings": {"count": "5", "token": "private-value"}}
        )
    ).status_code == 400
    assert (
        "private-value"
        not in (
            await admin_auth_client.put(
                path, json={"settings": {"count": 0, "token": "private-value"}}
            )
        ).text
    )
    values = {"count": 5, "enabled": False, "token": "saved-secret"}
    assert (
        await admin_auth_client.put(path, json={"settings": values})
    ).status_code == 200
    with pytest.raises(UserInputError):
        await app_context.settings_service.update_setting(
            "plugin_settings.typed_settings.count", "bad"
        )
    await app_context.settings.reload()
    assert (await admin_auth_client.get(path)).json()["settings"] == values
    async with app_context.db.session_manager() as session:
        stored = (
            await session.execute(
                select(PluginSetting).where(
                    PluginSetting.plugin_name == "typed_settings"
                )
            )
        ).scalar_one()
        assert stored.settings == values


async def test_settings_availability_for_untyped_plugins(
    admin_auth_client, plugin_factory, app_context
):
    await plugin_factory(
        "no_settings",
        "from bedrock_server_manager import PluginBase\nclass Empty(PluginBase):\n    version = '1.0'\n",
    )
    response = await admin_auth_client.get("/api/plugins")
    assert response.json()["plugins"]["no_settings"]["has_settings"] is False
    await app_context.plugin_service.set_setting("no_settings", "enabled_feature", True)
    response = await admin_auth_client.get("/api/plugins")
    assert response.json()["plugins"]["no_settings"]["has_settings"] is True


@pytest.mark.parametrize(
    "filename,values",
    [
        (
            "server_lifecycle_notifications",
            {
                "stop_warning_delay": 0,
                "post_stop_settle_delay": 0,
                "post_start_settle_delay": 0,
                "enable_notifications": False,
            },
        ),
        (
            "world_operation_notifications",
            {"notify_export": False, "notify_import": False, "notify_reset": False},
        ),
    ],
)
async def test_bundled_notification_settings(
    admin_auth_client, plugin_factory, filename, values
):
    from pathlib import Path
    import bedrock_server_manager.plugins.default as bundled

    plugin = await plugin_factory(
        filename, (Path(bundled.__file__).parent / (filename + ".py")).read_text()
    )
    path = f"/api/plugins/{filename}/settings"
    response = await admin_auth_client.get(path)
    assert response.status_code == 200
    assert response.json()["settings_schema"]["additionalProperties"] is False
    assert (
        await admin_auth_client.put(path, json={"settings": values})
    ).status_code == 200
    for key, value in values.items():
        assert await plugin.get_plugin_setting(key) == value
    if filename == "server_lifecycle_notifications":
        assert (
            await admin_auth_client.put(
                path, json={"settings": {"stop_warning_delay": -1}}
            )
        ).status_code == 400
        await plugin._send_ingame_message("missing", "test", "test")
    else:
        await plugin.send_export_warning(server_name="missing")
        await plugin.send_import_warning(server_name="missing")
        await plugin.send_reset_warning(server_name="missing")


async def test_backup_settings_use_live_valid_server_choices(
    admin_auth_client, plugin_factory, real_bedrock_server, app_context
):
    from pathlib import Path
    import bedrock_server_manager.plugins.default as bundled

    plugin = await plugin_factory(
        "backup_settings",
        (Path(bundled.__file__).parent / "backup_on_start.py").read_text(),
    )
    name = real_bedrock_server.server_name
    path = "/api/plugins/backup_settings/settings"
    data = (await admin_auth_client.get(path)).json()
    assert data["settings"]["servers"] == []
    assert name in data["settings_schema"]["properties"]["servers"]["items"]["enum"]
    assert (
        await admin_auth_client.put(path, json={"settings": {"servers": [name]}})
    ).status_code == 200
    assert (
        await admin_auth_client.put(path, json={"settings": {"servers": ["missing"]}})
    ).status_code == 400
    result = await plugin.api.server.get_valid_server_names(request={})
    assert name in result.server_names
    Path(real_bedrock_server.paths.server_properties_path).unlink()
    assert (
        name
        not in (await plugin.api.server.get_valid_server_names(request={})).server_names
    )
    assert (
        await admin_auth_client.put(path, json={"settings": {"servers": [name]}})
    ).status_code == 400
    assert (
        name
        not in (await admin_auth_client.get(path)).json()["settings_schema"][
            "properties"
        ]["servers"]["items"]["enum"]
    )
    assert (
        await admin_auth_client.put(path, json={"settings": {"servers": []}})
    ).status_code == 200
