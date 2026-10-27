"""Plugin settings schemas govern normal transactional writes in each scope."""

import asyncio

import pytest

from bedrock_server_manager.backups.contents import (
    DEFAULT_COMPONENTS,
    SERVER_PACK_COMPONENTS,
)
from bedrock_server_manager.error import UserInputError
from bedrock_server_manager.state.settings import BackupSettings, SettingsState

SOURCE = """
from pydantic import BaseModel, ConfigDict, Field
from bedrock_server_manager import PluginBase
class Profile(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    a: int = Field(default=1, ge=0, le=10)
    b: bool = False
class Own(BaseModel):
    enabled: bool = True
class TestPlugin(PluginBase):
    version = "1.0.0"
    settings_model = Own
    global_settings_model = Profile
    server_settings_model = Profile
"""


async def test_scoped_defaults_isolation_and_http_schema(
    admin_auth_client, plugin_factory, app_context
):
    plugin = await plugin_factory("profiles", SOURCE)
    await app_context.server_service.register_or_update_server("one")
    await app_context.server_service.register_or_update_server("two")
    path = "/api/plugins/profiles/settings"
    own = (await admin_auth_client.get(path)).json()
    assert own["settings"] == {"enabled": True}
    assert await plugin.get_plugin_settings(scope="global") == {"a": 1, "b": False}
    assert (
        "profiles" not in app_context.state.settings.custom
    )  # reading defaults does not persist
    for scope, server in (("global", None), ("server", "one")):
        params = {"scope": scope, **({"server_name": server} if server else {})}
        response = await admin_auth_client.get(path, params=params)
        assert response.status_code == 200, response.text
        assert response.json()["settings_schema"]["properties"]["a"]["maximum"] == 10
        saved = await admin_auth_client.put(
            path, json={**params, "settings": {"a": 3, "b": True}}
        )
        assert saved.status_code == 200, saved.text
    assert await plugin.get_plugin_setting("a", scope="global") == 3
    assert await plugin.get_plugin_setting("a", scope="server", server_name="one") == 3
    assert await plugin.get_plugin_setting("a", scope="server", server_name="two") == 1
    assert (await admin_auth_client.get(path)).json()["settings"] == own["settings"]
    bad = await admin_auth_client.put(
        path, json={"scope": "server", "server_name": "one", "settings": {"a": 99}}
    )
    assert bad.status_code == 400
    assert await plugin.get_plugin_setting("a", scope="server", server_name="one") == 3
    assert (
        await admin_auth_client.get(path, params={"scope": "server"})
    ).status_code in (400, 422)


async def test_all_normal_writes_validate_before_database_and_state_commit(
    plugin_factory, app_context
):
    plugin = await plugin_factory("profiles", SOURCE)
    await app_context.server_service.register_or_update_server("one")
    await plugin.set_plugin_settings({"a": 2}, scope="global")
    await plugin.set_plugin_settings({"a": 4}, scope="server", server_name="one")
    global_before = app_context.state.settings.to_dict()
    server_before = app_context.state.servers.get("one").model_dump()
    for key, value in (
        ("custom.profiles.a", -1),
        ("custom", {"profiles": {"a": "bad"}}),
    ):
        with pytest.raises(UserInputError):
            await app_context.settings_service.update_setting(key, value)
    with pytest.raises(UserInputError):
        await app_context.server_service.update_setting(
            "one", "custom.profiles.a", "bad"
        )
    with pytest.raises(UserInputError):
        await app_context.server_service.register_or_update_server(
            "one", custom={"profiles": {"a": -1}}
        )
    assert app_context.state.settings.to_dict() == global_before
    assert app_context.state.servers.get("one").model_dump() == server_before
    async with app_context.storage.transaction() as session:
        row = await app_context.storage.server_repo.get_server_by_name(session, "one")
        assert row.custom["profiles"] == {"a": 4, "b": False}
    await asyncio.gather(
        plugin.set_plugin_setting("a", 7, scope="global"),
        plugin.set_plugin_setting("b", True, scope="global"),
    )
    assert await plugin.get_plugin_settings(scope="global") == {"a": 7, "b": True}


async def test_unregistered_scopes_are_rejected_and_models_survive_disable(
    plugin_factory, app_context
):
    plugin = await plugin_factory("profiles", SOURCE)
    await plugin.set_plugin_setting("a", 2, scope="global")
    await app_context.plugin_service.set_enabled("profiles", False)
    assert (
        app_context.plugin_service.get_settings_schema("profiles", "global") is not None
    )
    with pytest.raises(UserInputError):
        await app_context.plugin_service.replace_settings("missing", {"a": 1}, "global")
    assert "missing" not in app_context.state.settings.custom


def test_pack_flag_migration_is_persistent_and_idempotent():
    old = SettingsState.from_dict({"backups": {"include_server_packs": True}})
    assert set(old.backups.components) == set(
        DEFAULT_COMPONENTS + SERVER_PACK_COMPONENTS
    )
    assert "include_server_packs" not in old.to_dict()["backups"]
    again = SettingsState.from_dict(old.to_dict())
    assert again.backups.components == old.backups.components
    assert again.get("backups.include_server_packs") is None
    with pytest.raises(ValueError):
        again.set("backups.include_server_packs", False)
    assert (
        "include_server_packs" not in BackupSettings.model_json_schema()["properties"]
    )
    selected = BackupSettings(components=["world", "resource_packs"])
    assert selected.components == ["world", "resource_packs"]


async def test_restore_review_validates_declared_server_settings(
    populated_server, plugin_factory, app_context
):
    from pydantic import BaseModel, Field

    from bedrock_server_manager.error import BackupRestoreError

    plugin = await plugin_factory("profiles", SOURCE)
    name = populated_server.server_name
    await plugin.set_plugin_settings({"a": 2}, scope="server", server_name=name)
    backup = await populated_server.backups.create_snapshot(
        mode="selected", components=["bsm_settings"]
    )

    class NewPolicy(BaseModel):
        a: int = Field(ge=5)
        b: bool = False

    app_context.plugin_service.server_settings_models["profiles"] = NewPolicy
    await plugin.set_plugin_settings({"a": 6}, scope="server", server_name=name)
    with pytest.raises(BackupRestoreError, match="Selected configuration is invalid"):
        await populated_server.backups.plan_restore(
            backup.backup_id, ["bsm_settings"], dry_run=True
        )
    assert app_context.state.servers.get(name).custom["profiles"]["a"] == 6
