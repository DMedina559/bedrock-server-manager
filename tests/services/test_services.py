from bedrock_server_manager.db.storage import Storage
from bedrock_server_manager.services.plugin_service import PluginService
from bedrock_server_manager.services.server_service import ServerService
from bedrock_server_manager.services.settings_service import SettingsService
from bedrock_server_manager.services.user_service import UserService
from bedrock_server_manager.state.app_state import AppState


async def test_settings_service_get_and_update(app_context):
    service = app_context.settings_service
    await service.update_setting("web.port", 9090)
    assert service.get("web.port") == 9090
    all_settings = await service.get_all_settings()
    assert all_settings["web"]["port"] == 9090


async def test_server_service_mutations(app_context):
    service = app_context.server_service
    config = await service.register_or_update_server(
        "srv1", installed_version="1.20", status="STOPPED", autostart=True
    )
    assert config.server_name == "srv1"
    assert config.autostart is True

    snapshot = service.get_server_state("srv1")
    assert snapshot is not None
    assert snapshot.autostart is True

    await service.set_autostart("srv1", False)
    assert app_context.state.servers.get("srv1").autostart is False


async def test_plugin_service_mutations(app_context):
    service = app_context.plugin_service
    plugin = await service.register_or_update_plugin(
        "test_plugin", enabled=True, version="1.0"
    )
    assert plugin.plugin_name == "test_plugin"
    assert plugin.enabled is True

    await service.set_enabled("test_plugin", False)
    assert app_context.state.plugins.get("test_plugin").enabled is False


async def test_user_service_mutations(app_context):
    service = app_context.user_service
    user = await service.register_or_update_user(
        "john_doe", role="admin", full_name="John Doe"
    )
    assert user.username == "john_doe"
    assert user.role == "admin"
    assert app_context.state.users.get("john_doe").full_name == "John Doe"


async def test_explicit_di_services(db):
    state = AppState()
    storage = Storage(db)

    server_svc = ServerService(state=state, storage=storage)
    plugin_svc = PluginService(state=state, storage=storage)
    user_svc = UserService(state=state, storage=storage)
    settings_svc = SettingsService(state=state, storage=storage)

    # Server mutation
    srv = await server_svc.register_or_update_server("di_srv", autostart=True)
    assert srv.server_name == "di_srv"
    assert state.servers.get("di_srv").autostart is True

    # Plugin mutation
    p = await plugin_svc.register_or_update_plugin("di_plugin", enabled=True)
    assert p.plugin_name == "di_plugin"
    assert state.plugins.get("di_plugin").enabled is True

    # User mutation
    u = await user_svc.register_or_update_user("di_user", role="admin")
    assert u.username == "di_user"
    assert state.users.get("di_user").role == "admin"

    # Setting mutation
    await settings_svc.update_setting("custom.key", "custom_val")
    assert state.settings.get("custom.key") == "custom_val"
