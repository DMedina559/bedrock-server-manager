import pytest
from unittest.mock import patch

from bedrock_server_manager.instances import (
    get_settings_instance,
    get_manager_instance,
    get_plugin_manager_instance,
    get_server_instance,
)


# Since these are singletons, we need to clear them between tests
@pytest.fixture(autouse=True)
def clear_instances():
    """Fixture to reset singleton instances before and after each test."""
    # Using patch to temporarily set the private instance variables to None
    with patch(
        "bedrock_server_manager.config.settings.Settings._instance", None, create=True
    ):
        with patch(
            "bedrock_server_manager.core.manager.BedrockServerManager._instance",
            None,
            create=True,
        ):
            with patch(
                "bedrock_server_manager.plugins.plugin_manager.PluginManager._instance",
                None,
                create=True,
            ):
                # For get_server_instance, the cache is a dictionary
                with patch(
                    "bedrock_server_manager.instances._server_instances",
                    {},
                    create=True,
                ):
                    yield


class TestInstances:
    def test_get_settings_instance_singleton(self):
        """Tests that get_settings_instance returns the same instance."""
        instance1 = get_settings_instance()
        instance2 = get_settings_instance()
        assert instance1 is instance2

    def test_get_manager_instance_singleton(self):
        """Tests that get_manager_instance returns the same instance."""
        instance1 = get_manager_instance()
        instance2 = get_manager_instance()
        assert instance1 is instance2

    def test_get_plugin_manager_instance_singleton(self):
        """Tests that get_plugin_manager_instance returns the same instance."""
        instance1 = get_plugin_manager_instance()
        instance2 = get_plugin_manager_instance()
        assert instance1 is instance2

    def test_get_server_instance_singleton(self):
        """Tests that get_server_instance returns the same instance for the same server."""
        instance1 = get_server_instance("server1")
        instance2 = get_server_instance("server1")
        assert instance1 is instance2

    def test_get_server_instance_different_servers(self):
        """Tests that get_server_instance returns different instances for different servers."""
        instance1 = get_server_instance("server1")
        instance2 = get_server_instance("server2")
        assert instance1 is not instance2
