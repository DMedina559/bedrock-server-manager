import pytest
from unittest.mock import MagicMock, patch
from bedrock_server_manager.plugins.plugin_manager import PluginManager


class TestPluginManager:
    def test_not_singleton(self, app_context):
        """Tests that the PluginManager is NOT a singleton."""
        pm1 = app_context.plugin_manager
        pm2 = PluginManager(app_context.settings)
        assert pm1 is not pm2

    def test_init_once(self, app_context):
        """Tests that the PluginManager initializes correctly."""
        pm = app_context.plugin_manager
        assert pm.settings is not None
        assert any("plugins" in str(path) for path in pm.plugin_dirs)
        assert "plugins.json" in str(pm.config_path)

    def test_load_and_save_config(self, app_context):
        """Tests loading and saving of the plugins.json file."""
        pm = app_context.plugin_manager

        # Test saving
        pm.plugin_config = {
            "plugin1": {
                "enabled": True,
                "version": "1.0",
                "description": "A test plugin.",
            }
        }
        pm._save_config()

        # Test loading
        pm.plugin_config = {}
        loaded_config = pm._load_config()
        assert "plugin1" in loaded_config
        assert loaded_config["plugin1"]["enabled"] is True
        assert loaded_config["plugin1"]["version"] == "1.0"
        assert loaded_config["plugin1"]["description"] == "A test plugin."

    def test_synchronize_config_with_disk(self, app_context):
        """Tests the synchronization of the config file with the plugins on disk."""
        pm = app_context.plugin_manager
        pm._synchronize_config_with_disk()

        # Check that valid plugins are in the config
        assert "plugin1" in pm.plugin_config
        assert pm.plugin_config["plugin1"]["version"] == "1.0"

    def test_load_plugins(self, app_context):
        """Tests the loading of enabled plugins."""
        pm = app_context.plugin_manager
        pm.plugin_config = {
            "plugin1": {"enabled": True, "version": "1.0"},
        }

        with patch.object(pm, "_synchronize_config_with_disk"):
            pm.load_plugins()

        # Check that the correct plugins are loaded
        assert len(pm.plugins) == 1
        plugin_names = [p.name for p in pm.plugins]
        assert "plugin1" in plugin_names

    def test_event_dispatch(self, app_context):
        """Tests the dispatching of events to plugins."""
        pm = app_context.plugin_manager
        pm.plugin_config = {"plugin1": {"enabled": True, "version": "1.0"}}

        with patch.object(pm, "_synchronize_config_with_disk"):
            pm.load_plugins()

        mock_plugin = pm.plugins[0]
        mock_plugin.on_unload = MagicMock()
        mock_plugin.on_unload.__name__ = (
            "on_unload"  # Add __name__ attribute to the mock
        )

        pm.trigger_event("on_unload")
        mock_plugin.on_unload.assert_called_once()

    def test_custom_event_system(self, app_context):
        """Tests the custom inter-plugin event system."""
        pm = app_context.plugin_manager

        callback = MagicMock()
        callback.__name__ = "my_callback"  # Add __name__ attribute to the mock
        pm.register_plugin_event_listener("my_plugin:my_event", callback, "my_plugin")
        pm.trigger_custom_plugin_event(
            "my_plugin:my_event", "another_plugin", "arg1", kwarg1="value1"
        )

        callback.assert_called_once_with(
            "arg1", kwarg1="value1", _triggering_plugin="another_plugin"
        )

    def test_reload_plugins(self, app_context):
        """Tests the reloading of plugins."""
        pm = app_context.plugin_manager
        pm.plugin_config = {"plugin1": {"enabled": True, "version": "1.0"}}
        with patch.object(pm, "_synchronize_config_with_disk"):
            pm.load_plugins()

        original_plugin = pm.plugins[0]
        original_plugin.on_unload = MagicMock()
        original_plugin.on_unload.__name__ = "on_unload"

        with patch.object(pm, "load_plugins") as mock_load_plugins:
            pm.reload()
            original_plugin.on_unload.assert_called_once()
            mock_load_plugins.assert_called_once()
