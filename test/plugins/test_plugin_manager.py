import pytest
import os
import json
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch, ANY

from bedrock_server_manager.plugins.plugin_manager import PluginManager
from bedrock_server_manager.plugins.plugin_base import PluginBase
from bedrock_server_manager.plugins.api_bridge import PluginAPI


# Helper function to create a temporary directory for tests
@pytest.fixture
def temp_plugin_env(tmp_path):
    """Creates a temporary directory structure for plugin tests."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir()
    default_plugins_dir = tmp_path / "default_plugins"
    default_plugins_dir.mkdir()

    # Create mock plugin files
    (plugins_dir / "valid_plugin.py").write_text(
        "from bedrock_server_manager.plugins.plugin_base import PluginBase\n"
        "class ValidPlugin(PluginBase):\n"
        "    version = '1.0'\n"
        "    def on_load(self):\n"
        "        pass\n"
    )
    (plugins_dir / "no_version_plugin.py").write_text(
        "from bedrock_server_manager.plugins.plugin_base import PluginBase\n"
        "class NoVersionPlugin(PluginBase):\n"
        "    def on_load(self):\n"
        "        pass\n"
    )
    (plugins_dir / "not_a_plugin.py").write_text("class NotAPlugin:\n    pass\n")
    (plugins_dir / "syntax_error_plugin.py").write_text("this is a syntax error\n")

    # Plugin with all the bells and whistles
    (plugins_dir / "full_featured_plugin.py").write_text(
        "from bedrock_server_manager.plugins.plugin_base import PluginBase\n"
        "import click\n"
        "from fastapi import APIRouter\n"
        "from pathlib import Path\n"
        "class FullFeaturedPlugin(PluginBase):\n"
        "    version = '2.0'\n"
        "    def on_load(self):\n"
        "        pass\n"
        "    def get_cli_commands(self):\n"
        "        @click.command()\n"
        "        def my_command():\n"
        "            pass\n"
        "        return [my_command]\n"
        "    def get_fastapi_routers(self):\n"
        "        router = APIRouter()\n"
        "        @router.get('/test')\n"
        "        def test_route():\n"
        "            return {'hello': 'world'}\n"
        "        return [router]\n"
        "    def get_template_paths(self):\n"
        "        return [Path(__file__).parent / 'templates']\n"
        "    def get_static_mounts(self):\n"
        "        return [('/static/full_featured', Path(__file__).parent / 'static', 'full_featured_static')]\n"
        "    def get_cli_menu_items(self):\n"
        "        return [{'name': 'My Menu Item', 'handler': self.on_load}]\n"
    )
    (plugins_dir / "templates").mkdir()
    (plugins_dir / "static").mkdir()

    return {
        "config_dir": config_dir,
        "plugins_dir": plugins_dir,
        "default_plugins_dir": default_plugins_dir,
    }


@pytest.fixture(autouse=True)
def cleanup_plugin_manager():
    """Fixture to reset the PluginManager singleton before and after each test."""
    PluginManager._instance = None
    yield
    PluginManager._instance = None


class TestPluginManager:
    def test_singleton(self):
        """Tests that the PluginManager is a singleton."""
        pm1 = PluginManager()
        pm2 = PluginManager()
        assert pm1 is pm2

    @pytest.fixture
    def isolated_plugin_manager(self, monkeypatch, temp_plugin_env):
        """Fixture to create a PluginManager isolated from default plugins."""
        mock_settings = MagicMock()
        mock_settings.get.return_value = str(temp_plugin_env["plugins_dir"])
        mock_settings.config_dir = str(temp_plugin_env["config_dir"])

        with patch(
            "bedrock_server_manager.plugins.plugin_manager.get_settings_instance",
            return_value=mock_settings,
        ):
            pm = PluginManager()
            # Use monkeypatch to isolate the plugin directories
            monkeypatch.setattr(pm, "plugin_dirs", [temp_plugin_env["plugins_dir"]])
            yield pm

    def test_init_once(self, isolated_plugin_manager, temp_plugin_env):
        """Tests that the PluginManager initializes correctly."""
        pm = isolated_plugin_manager
        assert pm.settings is not None
        assert any(path == temp_plugin_env["plugins_dir"] for path in pm.plugin_dirs)
        assert pm.config_path == temp_plugin_env["config_dir"] / "plugins.json"

    def test_load_and_save_config(self, isolated_plugin_manager, temp_plugin_env):
        """Tests loading and saving of the plugins.json file."""
        pm = isolated_plugin_manager

        # Test saving
        pm.plugin_config = {
            "valid_plugin": {
                "enabled": True,
                "version": "1.0",
                "description": "A valid plugin.",
            }
        }
        pm._save_config()

        # Test loading
        pm.plugin_config = {}
        loaded_config = pm._load_config()
        assert loaded_config == {
            "valid_plugin": {
                "enabled": True,
                "version": "1.0",
                "description": "A valid plugin.",
            }
        }

    def test_synchronize_config_with_disk(self, isolated_plugin_manager):
        """Tests the synchronization of the config file with the plugins on disk."""
        pm = isolated_plugin_manager
        pm._synchronize_config_with_disk()

        # Check that valid plugins are in the config
        assert "valid_plugin" in pm.plugin_config
        assert pm.plugin_config["valid_plugin"]["version"] == "1.0"
        assert "full_featured_plugin" in pm.plugin_config
        assert pm.plugin_config["full_featured_plugin"]["version"] == "2.0"

        # Check that invalid plugins are handled correctly
        assert "no_version_plugin" in pm.plugin_config
        assert pm.plugin_config["no_version_plugin"]["enabled"] is False
        assert "not_a_plugin" not in pm.plugin_config
        assert "syntax_error_plugin" not in pm.plugin_config

    def test_load_plugins(self, isolated_plugin_manager):
        """Tests the loading of enabled plugins."""
        pm = isolated_plugin_manager
        pm.plugin_config = {
            "valid_plugin": {"enabled": True, "version": "1.0"},
            "full_featured_plugin": {"enabled": True, "version": "2.0"},
            "no_version_plugin": {"enabled": True, "version": "N/A"},
        }

        with patch.object(pm, "_synchronize_config_with_disk") as mock_sync:
            pm.load_plugins()

        # Check that the correct plugins are loaded
        assert len(pm.plugins) == 2
        plugin_names = [p.name for p in pm.plugins]
        assert "valid_plugin" in plugin_names
        assert "full_featured_plugin" in plugin_names

        # Check that extension points are populated
        assert len(pm.plugin_fastapi_routers) == 1
        assert len(pm.plugin_template_paths) == 1
        assert len(pm.plugin_static_mounts) == 1

    def test_event_dispatch(self, isolated_plugin_manager):
        """Tests the dispatching of events to plugins."""
        pm = isolated_plugin_manager
        pm.plugin_config = {"valid_plugin": {"enabled": True, "version": "1.0"}}

        with patch.object(pm, "_synchronize_config_with_disk"):
            pm.load_plugins()

        mock_plugin = pm.plugins[0]
        mock_plugin.on_unload = MagicMock()
        mock_plugin.on_unload.__name__ = (
            "on_unload"  # Add __name__ attribute to the mock
        )

        pm.trigger_event("on_unload")
        mock_plugin.on_unload.assert_called_once()

    def test_custom_event_system(self, isolated_plugin_manager):
        """Tests the custom inter-plugin event system."""
        pm = isolated_plugin_manager

        callback = MagicMock()
        callback.__name__ = "my_callback"  # Add __name__ attribute to the mock
        pm.register_plugin_event_listener("my_plugin:my_event", callback, "my_plugin")
        pm.trigger_custom_plugin_event(
            "my_plugin:my_event", "another_plugin", "arg1", kwarg1="value1"
        )

        callback.assert_called_once_with(
            "arg1", kwarg1="value1", _triggering_plugin="another_plugin"
        )

    def test_reload_plugins(self, isolated_plugin_manager):
        """Tests the reloading of plugins."""
        pm = isolated_plugin_manager
        pm.plugin_config = {"valid_plugin": {"enabled": True, "version": "1.0"}}
        with patch.object(pm, "_synchronize_config_with_disk"):
            pm.load_plugins()

        original_plugin = pm.plugins[0]
        original_plugin.on_unload = MagicMock()
        original_plugin.on_unload.__name__ = "on_unload"

        with patch.object(pm, "load_plugins") as mock_load_plugins:
            pm.reload()
            original_plugin.on_unload.assert_called_once()
            mock_load_plugins.assert_called_once()
