from bedrock_server_manager.services.plugin_service import PluginService
from bedrock_server_manager.services.server_service import ServerService
from bedrock_server_manager.services.user_service import UserService


async def test_plugin_settings_keep_dotted_identity_and_snapshot_isolation(
    state, storage
):
    service = PluginService(state, storage)
    await service.set_setting("a.b", "nested.value", [False, 0])
    assert service.get_setting("a.b", "nested.value") == [False, 0]
    assert service.get_setting("a", "b.nested.value") is None
    value = service.get_setting("a.b", "nested.value")
    value.append(1)
    assert service.get_setting("a.b", "nested.value") == [False, 0]
    await service.register_or_update_plugin("a.b", enabled=False)
    assert service.get_setting("a.b", "nested.value") == [False, 0]


async def test_partial_updates_preserve_existing_fields(state, storage):
    servers = ServerService(state, storage)
    users = UserService(state, storage)
    await servers.register_or_update_server(
        "example", installed_version="1.2", status="RUNNING"
    )
    await servers.register_or_update_server("example")
    assert state.servers.get("example").installed_version == "1.2"
    assert state.servers.get("example").status == "RUNNING"
    await users.register_or_update_user(
        "owner", role="admin", theme="dark", is_active=False
    )
    await users.register_or_update_user("owner")
    assert state.users.get("owner").role == "admin"
    assert state.users.get("owner").theme == "dark"
    assert state.users.get("owner").is_active is False
