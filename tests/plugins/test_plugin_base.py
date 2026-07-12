import logging
from unittest.mock import MagicMock, patch

import pytest

from bedrock_server_manager.plugins.api_bridge import AppAPI
from bedrock_server_manager.plugins.plugin_base import PluginBase


@pytest.fixture
def mock_api():
    """Fixture providing a mock AppAPI."""
    return MagicMock(spec=AppAPI)


@pytest.fixture
def mock_logger():
    """Fixture providing a mock Logger."""
    return MagicMock(spec=logging.Logger)


def test_plugin_base_is_abstract():
    """Test PluginBase correctly enforces abstract instantiation restrictions."""
    with pytest.raises(TypeError) as exc_info:
        PluginBase("test", MagicMock(), MagicMock())
    assert "Can't instantiate abstract class" in str(exc_info.value)


class ValidPlugin(PluginBase):
    version = "1.2.3"

    def on_load(self):
        pass


class VersionlessPlugin(PluginBase):
    def on_load(self):
        pass


def test_concrete_plugin_initialization(mock_api, mock_logger):
    """Test successful initialization of a concrete plugin inheriting PluginBase."""
    plugin = ValidPlugin("my_plugin", mock_api, mock_logger)
    assert plugin.name == "my_plugin"
    assert plugin.api == mock_api
    assert plugin.logger == mock_logger
    assert plugin.version == "1.2.3"
    mock_logger.info.assert_called_with(
        "Plugin 'my_plugin' v1.2.3 initialized and active."
    )


def test_concrete_plugin_no_version_warning(mock_api, mock_logger):
    """Test plugin initialization warns when a class is missing the version property."""
    with patch.object(mock_logger, "warning") as mock_warning:
        plugin = VersionlessPlugin("no_version_plugin", mock_api, mock_logger)
        assert plugin.version == "N/A"
        mock_warning.assert_called_once_with(
            "Plugin 'no_version_plugin' class is missing a 'version' attribute or it's 'N/A'. "
            "This should be defined in the plugin class."
        )


def test_all_base_hooks_exist_and_callable(mock_api, mock_logger):
    """Test that all anticipated plugin lifecycle hooks are defined as methods on PluginBase and can be invoked cleanly."""
    plugin = ValidPlugin("my_plugin", mock_api, mock_logger)

    # Expected hook signatures
    hooks = [
        ("on_load", {}),
        ("on_unload", {}),
        ("before_server_start", {"server_name": "s1", "target_version": "1.0"}),
        ("after_server_start", {"server_name": "s1", "result": {}}),
        ("before_command_send", {"server_name": "s1", "command": "cmd"}),
        ("after_command_send", {"server_name": "s1", "command": "cmd", "result": {}}),
        ("before_backup", {"server_name": "s1", "backup_type": "full"}),
        ("after_backup", {"server_name": "s1", "backup_type": "full", "result": {}}),
        ("on_any_event", {"event_name": "foo", "arg1": "bar"}),
    ]

    for hook_name, kwargs in hooks:
        assert hasattr(plugin, hook_name)
        method = getattr(plugin, hook_name)
        assert callable(method)
        # Verify it doesn't throw NotImplementedError or anything
        method(**kwargs)


def test_extension_hooks_return_default_empty_lists(mock_api, mock_logger):
    """Test extension hooks return valid empty lists instead of NotImplemented or None."""
    plugin = ValidPlugin("my_plugin", mock_api, mock_logger)
    assert plugin.get_fastapi_routers() == []
    assert plugin.get_static_mounts() == []
