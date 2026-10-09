from bedrock_server_manager.plugins.plugin_manager import PluginManager


def test_not_singleton(app_context):
    """Test PluginManager is not a singleton enforcing context dependency."""
    pm1 = app_context.plugin_manager
    pm2 = PluginManager(
        state=app_context.state,
        storage=app_context.storage,
        settings=app_context.settings,
        app_context=app_context,
    )
    assert pm1 is not pm2


def test_init_once(app_context):
    """Test PluginManager initializes correctly and maps setting paths."""
    pm = app_context.plugin_manager
    assert pm.settings is not None
    assert any("plugins" in str(path) for path in pm.plugin_dirs)


async def test_load_and_save_config(db, app_context):
    """Test saving and loading arbitrary plugin JSON configuration dictionary mappings."""
    pm = app_context.plugin_manager

    pm.plugin_config = {
        "test_plugin_x": {
            "enabled": True,
            "version": "1.0",
            "description": "Mock description",
        }
    }

    await pm._save_config()

    # Reload from disk into fresh config dictionary
    pm.plugin_config = {}
    loaded = await pm._load_config()
    assert "test_plugin_x" in loaded
    assert loaded["test_plugin_x"]["enabled"] is True
    assert loaded["test_plugin_x"]["version"] == "1.0"


async def test_synchronize_config_with_disk(db, app_context):
    """Test synchronize configuration cleans up orphaned keys and adds loaded ones."""
    pm = app_context.plugin_manager
    # Disk discovery removes configuration entries without a plugin module.
    pm.plugin_config = {"phantom_plugin": {"enabled": True}}

    await pm._synchronize_config_with_disk()

    assert "phantom_plugin" not in pm.plugin_config


async def test_synchronize_config_preserves_app_state(db, app_context):
    """Test disk sync and _load_config do NOT reload or wipe AppState settings or user auth state."""
    from bedrock_server_manager.utils.auth import get_jwt_secret_key

    # Set up a secret key in settings
    await app_context.settings.set("web.jwt_secret_key", "persistent_secret_key_123")
    key_before = await get_jwt_secret_key(app_context.settings)
    assert key_before == "persistent_secret_key_123"

    pm = app_context.plugin_manager
    await pm._synchronize_config_with_disk()

    key_after = await get_jwt_secret_key(app_context.settings)
    assert key_after == "persistent_secret_key_123"


EVENT_PLUGIN = """
from bedrock_server_manager.plugins import PluginBase, app_event
class Listener(PluginBase):
    version = "1.0.0"
    def on_load(self):
        self.received = []
    @app_event("test:event")
    async def receive(self, *args, **kwargs):
        self.received.append((args, kwargs))
"""


async def test_load_plugins(app_context, plugin_factory):
    plugin = await plugin_factory("listener", EVENT_PLUGIN)
    assert app_context.plugin_manager.get_plugin_status("listener") == "LOADED"
    assert plugin in app_context.plugin_manager.plugins


async def test_custom_event_system(app_context, plugin_factory):
    plugin = await plugin_factory("listener", EVENT_PLUGIN)
    await app_context.plugin_manager.trigger_event(
        "test:event", "arg1", kw="val", _triggering_plugin="sender_plugin"
    )
    assert plugin.received == [
        (("arg1",), {"kw": "val", "_triggering_plugin": "sender_plugin"})
    ]


async def test_reload_plugins(app_context, plugin_factory):
    old_plugin = await plugin_factory("listener", EVENT_PLUGIN)
    manager = app_context.plugin_manager
    await manager.reload()
    assert manager.get_plugin_status("listener") == "LOADED"
    new_plugin = next(p for p in manager.plugins if p.api._plugin_name == "listener")
    assert new_plugin is not old_plugin
    await manager.trigger_event("test:event", payload="reloaded")
    assert new_plugin.received == [((), {"payload": "reloaded"})]
    assert old_plugin.received == []


def test_path_traversal_rejection(app_context):
    """Test PluginManager rejects path traversal and unsafe names in plugin discovery."""
    pm = app_context.plugin_manager

    assert pm._find_plugin_path("../secret") is None
    assert pm._find_plugin_path("../../etc/passwd") is None
    assert pm._find_plugin_path("foo/bar") is None
    assert pm._find_plugin_path("..") is None


async def test_event_dispatch_app_context_sanitization(app_context, plugin_factory):
    plugin = await plugin_factory("listener", EVENT_PLUGIN)
    await app_context.plugin_manager.dispatch_event(
        plugin, "test:event", app_context=app_context, payload="data"
    )
    assert plugin.received == [((), {"payload": "data"})]


async def test_topological_dependency_sorting(app_context):
    """Test inter-plugin dependency resolution sorts in correct topological order."""
    from bedrock_server_manager.plugins.plugin_base import PluginBase

    pm = app_context.plugin_manager

    class PluginA(PluginBase):
        version = "1.0.0"

    class PluginB(PluginBase):
        version = "1.0.0"
        dependencies = ["PluginA"]

    class PluginC(PluginBase):
        version = "1.0.0"
        dependencies = ["PluginB"]

    classes = {
        "PluginC": PluginC,
        "PluginA": PluginA,
        "PluginB": PluginB,
    }

    sorted_names = pm._sort_plugin_dependencies(classes)
    assert sorted_names == ["PluginA", "PluginB", "PluginC"]


async def test_granular_plugin_lifecycle(db, app_context, tmp_path):
    """Test load_plugin_by_name, unload_plugin_by_name, enable_plugin, disable_plugin, and reload_plugin."""
    pm = app_context.plugin_manager

    plugin_dir = pm.plugin_dirs[0]
    plugin_file = plugin_dir / "sample_test_plugin.py"
    plugin_code = """
from bedrock_server_manager.plugins.plugin_base import PluginBase

class SampleTestPlugin(PluginBase):
    version = "1.0.0"
    author = "Tester"
    description = "Sample test plugin"

    async def on_load(self):
        pass

    async def on_unload(self):
        pass
"""
    plugin_file.write_text(plugin_code)

    try:
        # Enable and load
        enabled = await pm.enable_plugin("sample_test_plugin", load_immediately=True)
        assert enabled is True
        assert pm.get_plugin_status("sample_test_plugin") == "LOADED"
        assert len(pm.plugins) == 1

        # Reload
        reloaded = await pm.reload_plugin("sample_test_plugin")
        assert reloaded is True
        assert pm.get_plugin_status("sample_test_plugin") == "LOADED"

        # Disable and unload
        disabled = await pm.disable_plugin(
            "sample_test_plugin", unload_immediately=True
        )
        assert disabled is True
        assert pm.get_plugin_status("sample_test_plugin") == "DISABLED"
        assert len(pm.plugins) == 0

    finally:
        if plugin_file.exists():
            plugin_file.unlink()


def test_plugin_status_tracking(app_context):
    """Test get_plugin_status returns correct statuses."""
    pm = app_context.plugin_manager

    assert pm.get_plugin_status("nonexistent_plugin") == "UNKNOWN"

    pm.plugin_config["disabled_plugin"] = {"enabled": False, "status": "DISABLED"}
    assert pm.get_plugin_status("disabled_plugin") == "DISABLED"

    pm.plugin_config["error_plugin"] = {"enabled": True, "status": "ERROR"}
    assert pm.get_plugin_status("error_plugin") == "ERROR"


async def test_failed_load_removes_partial_instance_and_provider(app_context):
    manager = app_context.plugin_manager
    path = manager.plugin_dirs[0] / "sample.py"
    path.write_text("""
from bedrock_server_manager.plugins import PluginBase
class FailingPlugin(PluginBase):
    version = "1.0.0"
    async def on_load(self):
        await self.api.runtime.register_data_provider("partial", lambda: 1)
        raise RuntimeError("load failed")
""")
    await app_context.plugin_service.register_or_update_plugin("sample", enabled=True)
    await manager._synchronize_config_with_disk()
    for _ in range(2):
        assert not await manager.load_plugin_by_name("sample")
        assert manager.plugins == []
        assert manager.get_plugin_status("sample") == "ERROR"
        assert app_context.connection_manager.get_data_provider("partial") is None


async def test_full_unload_removes_plugin_providers(app_context, plugin_factory):
    await plugin_factory(
        "sample",
        """
from bedrock_server_manager.plugins import PluginBase
class Provider(PluginBase):
    version = "1.0.0"
    async def on_load(self):
        await self.api.runtime.register_data_provider("sample", lambda: 1)
""",
    )
    assert app_context.connection_manager.get_data_provider("sample") is not None
    await app_context.plugin_manager.unload_plugins()
    assert app_context.connection_manager.get_data_provider("sample") is None


def test_runtime_snapshot_is_typed_and_independent(app_context):
    import pytest
    from pydantic import ValidationError

    manager = app_context.plugin_manager
    manager._set_runtime_status("sample", "LOADED")
    manager._event_listeners = {"example": {"sample": []}}
    snapshot = manager.get_plugin_runtime("sample")
    assert snapshot.loaded
    assert snapshot.registered_events == ["example"]
    snapshot.registered_events.clear()
    assert manager.get_plugin_runtime("sample").registered_events == ["example"]
    with pytest.raises(ValidationError):
        manager._set_runtime_status("sample", "INVALID")
    assert manager.get_plugin_status("sample") == "LOADED"


async def test_plugin_http_routes_follow_load_and_unload(
    app_context, running_app, admin_auth_client, plugin_factory
):
    manager = app_context.plugin_manager
    await plugin_factory(
        "sample",
        """
from fastapi import APIRouter
from bedrock_server_manager.plugins import PluginBase
class WebPlugin(PluginBase):
    version = "1.0.0"
    def get_fastapi_routers(self):
        router = APIRouter()
        router.add_api_route("/sample", lambda: {"ok": True}, operation_id="sample")
        return [router]
""",
    )
    for _ in range(2):
        assert "/sample" in running_app.openapi()["paths"]
        assert (await admin_auth_client.get("/sample")).json() == {"ok": True}
        await manager.unload_plugins()
        assert "/sample" not in running_app.openapi()["paths"]
        assert (await admin_auth_client.get("/sample")).status_code == 404
        assert not manager.plugin_fastapi_routers
        assert await manager.load_plugin_by_name("sample")


async def test_sync_plugin_loop_unload_waits_for_worker(app_context):
    import asyncio
    import threading
    from types import SimpleNamespace

    from bedrock_server_manager.utils.threads import run_in_thread

    started, released = threading.Event(), threading.Event()

    def worker(cancellation_event):
        started.set()
        cancellation_event.wait()
        released.wait()

    manager = app_context.plugin_manager
    manager.plugins = [
        SimpleNamespace(name="sample", api=SimpleNamespace(_plugin_name="sample"))
    ]
    task = asyncio.create_task(run_in_thread(worker))
    manager.plugin_tasks = {"sample": [task]}
    await asyncio.to_thread(started.wait)
    unload = asyncio.create_task(manager.unload_plugins())
    await asyncio.sleep(0)
    assert not unload.done()
    released.set()
    await unload
    assert task.cancelled()
    assert not manager.plugin_tasks


async def test_bundled_plugins_load_through_dynamic_manager(
    app_context, monkeypatch, caplog
):
    """Bundled files must also work under the runtime bsm_plugins namespace."""
    import logging
    import sys
    from pathlib import Path

    from bedrock_server_manager.plugins import default as bundled_plugins

    directory = Path(bundled_plugins.__file__).parent
    names = {path.stem for path in directory.glob("*.py") if path.stem != "__init__"}
    for name in names:
        monkeypatch.delitem(sys.modules, f"bsm_plugins.{name}", raising=False)
    manager = app_context.plugin_manager
    manager.plugin_dirs = [directory]
    caplog.clear()
    await manager._synchronize_config_with_disk()
    assert set(manager._discovered_classes) == names
    for name in names:
        manager.plugin_config[name]["enabled"] = True
    await manager._save_config()
    await manager.load_plugins()
    assert {type(plugin).__module__ for plugin in manager.plugins} == {
        f"bsm_plugins.{name}" for name in names
    }
    assert not [record for record in caplog.records if record.levelno >= logging.ERROR]


async def test_example_listener_logs_metadata_without_payload(
    plugin_factory, app_context, caplog
):
    import logging
    from pathlib import Path

    source = Path(__file__).resolve().parents[2] / "plugins" / "pong_plugin.py"
    await plugin_factory("pong_example", source.read_text())
    caplog.clear()
    with caplog.at_level(logging.DEBUG):
        await app_context.plugin_manager.trigger_event(
            "pingplugin:ping",
            "private positional data",
            server_name="example",
            data={"message": "private payload data"},
            _triggering_plugin="example_sender",
        )
    assert "private positional data" not in caplog.text
    assert "private payload data" not in caplog.text
    assert "example_sender" in caplog.text
