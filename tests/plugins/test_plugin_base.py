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


@pytest.mark.skip
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
