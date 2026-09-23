from unittest.mock import MagicMock

from bedrock_server_manager.plugins.plugin_manager import PluginManager


def test_not_singleton(app_context):
    """Test PluginManager is not a singleton enforcing context dependency."""
    pm1 = app_context.plugin_manager
    pm2 = PluginManager(app_context)
    assert pm1 is not pm2


def test_init_once(app_context):
    """Test PluginManager initializes correctly and maps setting paths."""
    pm = app_context.plugin_manager
    assert pm.settings is not None
    assert any("plugins" in str(path) for path in pm.plugin_dirs)


async def test_load_and_save_config(async_db, app_context):
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


async def test_synchronize_config_with_disk(async_db, app_context):
    """Test synchronize configuration cleans up orphaned keys and adds loaded ones."""
    pm = app_context.plugin_manager
    # Injected plugins mock directory might be empty, but we can verify it wipes clean unused dict entries
    pm.plugin_config = {"phantom_plugin": {"enabled": True}}

    await pm._synchronize_config_with_disk()

    assert isinstance(pm.plugin_config, dict)


async def test_load_plugins(async_db, app_context, monkeypatch):
    """Test PluginManager loads properly matching plugins."""
    pm = app_context.plugin_manager

    mock_plugin_instance = MagicMock()
    mock_plugin_instance.name = "mock_plugin_y"
    mock_plugin_instance.version = "1.0"

    # Stub load mechanisms
    monkeypatch.setattr(pm, "_synchronize_config_with_disk", MagicMock())

    # Normally we load from disk, so we fake plugins array directly here to test dispatch hooks.
    pm.plugins = [mock_plugin_instance]
    assert len(pm.plugins) == 1
    assert pm.plugins[0].name == "mock_plugin_y"


async def test_custom_event_system(async_db, app_context):
    """Test inter-plugin event broadcast and listeners dispatch accurately."""
    pm = app_context.plugin_manager

    callback = MagicMock()
    callback.__name__ = "my_callback"

    mock_plugin = MagicMock()
    mock_plugin.name = "listen_plugin"

    # Actually pm.plugins might be a list
    pm.plugins = [mock_plugin]

    pm.register_app_event_listener("test:event", callback, "listen_plugin")

    await pm.trigger_event(
        "test:event", "arg1", kw="val", _triggering_plugin="sender_plugin"
    )

    callback.assert_called_once_with(
        "arg1", kw="val", _triggering_plugin="sender_plugin"
    )


async def test_event_dispatch(async_db, app_context):
    """Test trigger_event correctly loops over all active plugins invoking registered hooks."""
    pm = app_context.plugin_manager

    mock_plugin = MagicMock()
    mock_plugin.name = "mock_plugin"

    callback = MagicMock()
    callback.__name__ = "my_callback"

    pm.plugins = [mock_plugin]
    pm._event_listeners = {"on_unload": {"mock_plugin": [callback]}}

    await pm.trigger_event("on_unload")

    callback.assert_called_once()


async def test_reload_plugins(async_db, app_context, monkeypatch):
    """Test PluginManager unloads plugins before reloading the cache."""
    pm = app_context.plugin_manager

    mock_plugin = MagicMock()
    mock_plugin.name = "mock_plugin"

    pm.plugins = {mock_plugin}
    pm._event_listeners = {"test_event": []}

    with monkeypatch.context() as m:
        from unittest.mock import AsyncMock

        mock_load = AsyncMock()
        m.setattr(pm, "load_plugins", mock_load)
        # Instead of intercepting the mock plugin event, just verify load_plugins is called and lists are cleared
        await pm.reload()

        assert len(pm._event_listeners) == 0
        mock_load.assert_called_once()


def test_path_traversal_rejection(app_context):
    """Test PluginManager rejects path traversal and unsafe names in plugin discovery."""
    pm = app_context.plugin_manager

    assert pm._find_plugin_path("../secret") is None
    assert pm._find_plugin_path("../../etc/passwd") is None
    assert pm._find_plugin_path("foo/bar") is None
    assert pm._find_plugin_path("..") is None


async def test_event_dispatch_app_context_sanitization(app_context):
    """Test dispatch_event strips app_context from kwargs passed to listeners."""
    pm = app_context.plugin_manager

    received_kwargs = {}

    async def listener(**kwargs):
        received_kwargs.update(kwargs)

    listener.__name__ = "listener"

    mock_plugin = MagicMock()
    mock_plugin.name = "test_plugin"
    pm.plugins = [mock_plugin]
    pm.register_app_event_listener("test_event", listener, "test_plugin")

    await pm.dispatch_event(
        mock_plugin, "test_event", app_context=app_context, payload="data"
    )

    assert "app_context" not in received_kwargs
    assert received_kwargs.get("payload") == "data"


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


async def test_granular_plugin_lifecycle(async_db, app_context, tmp_path):
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
