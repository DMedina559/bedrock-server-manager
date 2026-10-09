from bedrock_server_manager.context import AppContext
from bedrock_server_manager.core.bedrock_server import BedrockServer
from bedrock_server_manager.state.app_state import AppState


def test_app_context_initialization(app_context):
    assert app_context._api is None
    assert app_context._task_manager is None
    assert app_context.api is app_context.api
    assert app_context.task_manager is app_context.task_manager


async def test_app_context_load_without_prior_settings(db):
    context = AppContext()
    context._db = db
    try:
        await context.load()
        assert context.settings.get("web.port") > 0
    finally:
        await context.shutdown()


async def test_reload_preserves_persisted_settings_and_restarts_monitors(app_context):
    await app_context.settings.set("custom.integration", {"saved": True})
    app_context.resource_monitor.start()
    old_task = app_context.resource_monitor._task
    await app_context.reload()
    assert old_task.done()
    assert app_context.resource_monitor._task is not old_task
    assert app_context.settings.get("custom.integration") == {"saved": True}


def test_get_server_creates_and_caches(app_context):
    first = app_context.get_server("cached_server")
    assert isinstance(first, BedrockServer)
    assert app_context.get_server("cached_server") is first


async def test_remove_running_server_stops_process_and_removes_cache(
    app_context, real_bedrock_server
):
    await real_bedrock_server.start()
    child = real_bedrock_server.process._process
    assert child is not None
    await app_context.remove_server(real_bedrock_server.server_name)
    assert child.returncode is not None
    assert real_bedrock_server.server_name not in app_context._servers
    assert (
        real_bedrock_server.server_name
        not in app_context.bedrock_process_manager.servers
    )


async def test_remove_stopped_server_removes_cache(app_context, real_bedrock_server):
    await app_context.remove_server(real_bedrock_server.server_name)
    assert real_bedrock_server.server_name not in app_context._servers


async def test_remove_nonexistent_server_is_idempotent(app_context):
    await app_context.remove_server("does_not_exist")
    await app_context.remove_server("does_not_exist")


async def test_shutdown_drains_monitors_and_persists_state(app_context):
    await app_context.settings.set("custom.shutdown", "saved")
    app_context.resource_monitor.start()
    monitor = app_context.resource_monitor._task
    await app_context.bedrock_process_manager.start()
    process_monitor = app_context.bedrock_process_manager.monitoring_task
    await app_context.shutdown()
    assert monitor.done()
    assert process_monitor.done()
    restored = AppState()
    await app_context.storage.load_state(restored)
    assert restored.settings.get("custom.shutdown") == "saved"
