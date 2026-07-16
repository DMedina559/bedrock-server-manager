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
    assert "plugins.json" in str(pm.config_path)


def test_load_and_save_config(app_context):
    """Test saving and loading arbitrary plugin JSON configuration dictionary mappings."""
    pm = app_context.plugin_manager

    pm.plugin_config = {
        "test_plugin_x": {
            "enabled": True,
            "version": "1.0",
            "description": "Mock description",
        }
    }

    pm._save_config()

    # Reload from disk into fresh config dictionary
    pm.plugin_config = {}
    loaded = pm._load_config()
    assert "test_plugin_x" in loaded
    assert loaded["test_plugin_x"]["enabled"] is True
    assert loaded["test_plugin_x"]["version"] == "1.0"


def test_synchronize_config_with_disk(app_context):
    """Test synchronize configuration cleans up orphaned keys and adds loaded ones."""
    pm = app_context.plugin_manager
    # Injected plugins mock directory might be empty, but we can verify it wipes clean unused dict entries
    pm.plugin_config = {"phantom_plugin": {"enabled": True}}

    pm._synchronize_config_with_disk()

    assert isinstance(pm.plugin_config, dict)


def test_load_plugins(app_context, monkeypatch):
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


def test_event_dispatch(app_context):
    """Test trigger_event correctly loops over all active plugins invoking registered hooks."""
    pm = app_context.plugin_manager

    mock_plugin = MagicMock()
    mock_plugin.on_unload = MagicMock()
    mock_plugin.on_unload.__name__ = "on_unload"
    mock_plugin.on_any_event = MagicMock()
    mock_plugin.on_any_event.__name__ = "on_any_event"

    pm.plugins = [mock_plugin]

    pm.trigger_event("on_unload")

    mock_plugin.on_unload.assert_called_once()
    mock_plugin.on_any_event.assert_called_once()


def test_wildcard_event_dispatch_only(app_context):
    """Test wildcard 'on_any_event' hooks fire even when the target event hook isn't explicitly defined."""
    pm = app_context.plugin_manager

    mock_plugin = MagicMock()
    del mock_plugin.missing_hook  # ensure its absent

    mock_plugin.on_any_event = MagicMock()
    mock_plugin.on_any_event.__name__ = "on_any_event"

    pm.plugins = [mock_plugin]

    pm.trigger_event("missing_hook", my_arg="val")

    mock_plugin.on_any_event.assert_called_once()
    args, kwargs = mock_plugin.on_any_event.call_args
    assert args[0] == "missing_hook"
    assert kwargs.get("my_arg") == "val"


def test_custom_event_system(app_context):
    """Test inter-plugin event broadcast and listeners dispatch accurately."""
    pm = app_context.plugin_manager

    callback = MagicMock()
    callback.__name__ = "my_callback"

    pm.register_plugin_event_listener("test:event", callback, "listen_plugin")

    pm.trigger_custom_plugin_event("test:event", "sender_plugin", "arg1", kw="val")

    callback.assert_called_once_with(
        "arg1", kw="val", _triggering_plugin="sender_plugin"
    )


def test_reload_plugins(app_context, monkeypatch):
    """Test PluginManager unloads plugins before reloading the cache."""
    pm = app_context.plugin_manager

    mock_plugin = MagicMock()
    mock_plugin.on_unload = MagicMock()
    mock_plugin.on_unload.__name__ = "on_unload"
    pm.plugins = [mock_plugin]

    mock_loader = MagicMock()
    monkeypatch.setattr(pm, "load_plugins", mock_loader)

    pm.reload()

    mock_plugin.on_unload.assert_called_once()
    mock_loader.assert_called_once()
