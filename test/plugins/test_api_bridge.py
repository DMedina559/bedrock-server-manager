import pytest
from unittest.mock import MagicMock, patch
from bedrock_server_manager.plugins.api_bridge import (
    plugin_method,
    PluginAPI,
    _api_registry,
)


# Fixture to clear the API registry before each test
@pytest.fixture(autouse=True)
def clear_api_registry():
    _api_registry.clear()
    yield
    _api_registry.clear()


def test_plugin_method_decorator():
    """Tests that the plugin_method decorator correctly registers a function."""

    @plugin_method("my_test_api")
    def my_test_function():
        return "hello"

    assert "my_test_api" in _api_registry
    assert _api_registry["my_test_api"] == my_test_function
    assert my_test_function() == "hello"


def test_plugin_method_decorator_overwrite_warning(caplog):
    """Tests that the plugin_method decorator logs a warning when overwriting an API."""

    @plugin_method("my_test_api")
    def my_test_function():
        return "hello"

    @plugin_method("my_test_api")
    def my_new_test_function():
        return "world"

    assert "Overwriting existing API function 'my_test_api'" in caplog.text


class TestPluginAPI:
    """Tests for the PluginAPI class."""

    @pytest.fixture
    def mock_plugin_manager(self):
        """Fixture for a mocked PluginManager."""
        return MagicMock()

    @pytest.fixture
    def mock_app_context(self):
        """Fixture for a mocked AppContext."""
        return MagicMock()

    @pytest.fixture
    def plugin_api(self, mock_plugin_manager, mock_app_context):
        """Fixture for a PluginAPI instance."""
        return PluginAPI("test_plugin", mock_plugin_manager, mock_app_context)

    def test_getattr_success(self, plugin_api):
        """Tests that __getattr__ successfully retrieves a registered API function."""

        @plugin_method("my_test_api")
        def my_test_function():
            return "hello"

        assert plugin_api.my_test_api() == "hello"

    def test_getattr_fail(self, plugin_api):
        """Tests that __getattr__ raises an AttributeError for an unregistered function."""
        with pytest.raises(AttributeError):
            plugin_api.non_existent_api()

    def test_list_available_apis(self, plugin_api):
        """Tests that list_available_apis returns a correct list of registered APIs."""

        @plugin_method("my_test_api")
        def my_test_function(param1: str, param2: int = 5) -> str:
            """This is a test function."""
            return f"{param1}, {param2}"

        api_list = plugin_api.list_available_apis()

        assert len(api_list) == 1
        assert api_list[0]["name"] == "my_test_api"
        assert api_list[0]["docstring"] == "This is a test function."
        assert len(api_list[0]["parameters"]) == 2
        assert api_list[0]["parameters"][0]["name"] == "param1"
        assert api_list[0]["parameters"][1]["name"] == "param2"
        assert api_list[0]["parameters"][1]["default"] == 5

    def test_listen_for_event(self, plugin_api, mock_plugin_manager):
        """Tests that listen_for_event calls the PluginManager's registration method."""

        def my_callback():
            pass

        plugin_api.listen_for_event("my_event", my_callback)
        mock_plugin_manager.register_plugin_event_listener.assert_called_once_with(
            "my_event", my_callback, "test_plugin"
        )

    def test_send_event(self, plugin_api, mock_plugin_manager):
        """Tests that send_event calls the PluginManager's trigger method."""
        plugin_api.send_event("my_event", 1, 2, key="value")
        mock_plugin_manager.trigger_custom_plugin_event.assert_called_once_with(
            "my_event", "test_plugin", 1, 2, key="value"
        )

    def test_get_plugin_html_pages(self, plugin_api, mock_plugin_manager):
        """Tests that get_plugin_html_pages calls the PluginManager's method."""
        plugin_api.get_plugin_html_pages()
        mock_plugin_manager.get_html_render_routes.assert_called_once()
