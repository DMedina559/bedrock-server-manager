import logging

from bedrock_server_manager.plugins.api_bridge import create_app_api
from bedrock_server_manager.plugins.plugin_base import PluginBase


class ValidPlugin(PluginBase):
    version = "1.2.3"


class VersionlessPlugin(PluginBase):
    pass


def test_concrete_plugin_initialization(app_context, caplog):
    api = create_app_api("my_plugin", app_context)
    logger = logging.getLogger("test.plugin")
    with caplog.at_level(logging.INFO):
        plugin = ValidPlugin("my_plugin", api, logger)
    assert plugin.name == "my_plugin"
    assert plugin.api is api
    assert plugin.logger is logger
    assert plugin.version == "1.2.3"
    assert "Plugin 'my_plugin' v1.2.3 initialized and active." in caplog.text


def test_concrete_plugin_no_version_warning(app_context, caplog):
    api = create_app_api("no_version_plugin", app_context)
    plugin = VersionlessPlugin(
        "no_version_plugin", api, logging.getLogger("test.plugin")
    )
    assert plugin.version == "N/A"
    assert "missing a 'version' attribute" in caplog.text
