import pytest
from unittest.mock import MagicMock, patch
import logging
from pathlib import Path

from bedrock_server_manager.plugins.plugin_base import PluginBase
from bedrock_server_manager.plugins.api_bridge import PluginAPI


@pytest.fixture
def mock_api():
    """Fixture for a mocked PluginAPI."""
    return MagicMock(spec=PluginAPI)


@pytest.fixture
def mock_logger():
    """Fixture for a mocked Logger."""
    return MagicMock(spec=logging.Logger)


def test_plugin_base_is_abc():
    """Tests that PluginBase cannot be instantiated directly."""
    with pytest.raises(TypeError):
        PluginBase(
            "test_plugin", MagicMock(spec=PluginAPI), MagicMock(spec=logging.Logger)
        )


class TestConcretePlugin:
    """Tests for a concrete implementation of PluginBase."""

    class ConcretePlugin(PluginBase):
        version = "1.0.0"

        def on_load(self):
            pass

    class NoVersionPlugin(PluginBase):
        def on_load(self):
            pass

    def test_init_success(self, mock_api, mock_logger):
        """Tests successful initialization of a concrete plugin."""
        plugin = self.ConcretePlugin("my_plugin", mock_api, mock_logger)
        assert plugin.name == "my_plugin"
        assert plugin.api == mock_api
        assert plugin.logger == mock_logger
        assert plugin.version == "1.0.0"
        mock_logger.info.assert_called_with(
            "Plugin 'my_plugin' v1.0.0 initialized and active."
        )

    def test_init_no_version_warning(self, mock_api, mock_logger):
        """Tests that a warning is logged if a plugin is missing a version."""
        with patch.object(mock_logger, "warning") as mock_warning:
            plugin = self.NoVersionPlugin("no_version_plugin", mock_api, mock_logger)
            assert plugin.version == "N/A"
            mock_warning.assert_called_once_with(
                "Plugin 'no_version_plugin' class is missing a 'version' attribute or it's 'N/A'. "
                "This should be defined in the plugin class."
            )

    def test_all_hooks_exist_and_are_callable(self, mock_api, mock_logger):
        """Tests that all hook methods exist and can be called without errors."""
        plugin = self.ConcretePlugin("my_plugin", mock_api, mock_logger)

        # A selection of hooks to test for existence and callability
        hooks = [
            ("on_load", {}),
            ("on_unload", {}),
            (
                "before_server_start",
                {"server_name": "server1", "target_version": "1.0.0"},
            ),
            (
                "after_server_start",
                {"server_name": "server1", "result": {"status": "success"}},
            ),
            ("before_command_send", {"server_name": "server1", "command": "say hello"}),
            (
                "after_command_send",
                {
                    "server_name": "server1",
                    "command": "say hello",
                    "result": {"status": "success"},
                },
            ),
            ("before_backup", {"server_name": "server1", "backup_type": "world"}),
            (
                "after_backup",
                {
                    "server_name": "server1",
                    "backup_type": "world",
                    "result": {"status": "success"},
                },
            ),
        ]

        for hook_name, kwargs in hooks:
            assert hasattr(plugin, hook_name)
            method = getattr(plugin, hook_name)
            assert callable(method)
            try:
                method(**kwargs)
            except Exception as e:
                pytest.fail(f"Hook '{hook_name}' raised an exception: {e}")

    def test_extension_hooks_return_empty_lists(self, mock_api, mock_logger):
        """Tests that the extension hooks return empty lists by default."""
        plugin = self.ConcretePlugin("my_plugin", mock_api, mock_logger)

        assert plugin.get_fastapi_routers() == []
        assert plugin.get_template_paths() == []
        assert plugin.get_static_mounts() == []
