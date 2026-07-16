from unittest.mock import MagicMock

import pytest

from bedrock_server_manager.plugins.api_bridge import AppAPI, _api_registry, api_method


@pytest.fixture(autouse=True)
def clear_api_registry():
    """Fixture to ensure the global API registry is cleared before and after each test."""
    _api_registry.clear()
    yield
    _api_registry.clear()


def test_api_method_decorator():
    """Test the api_method decorator correctly registers a function in the global registry."""

    @api_method("my_test_api")
    def my_test_function():
        return "hello"

    assert "my_test_api" in _api_registry
    assert _api_registry["my_test_api"][0] == my_test_function
    assert my_test_function() == "hello"


def test_api_method_decorator_overwrite_warning(caplog):
    """Test api_method logs a warning when a function name is overwritten."""

    @api_method("my_test_api")
    def my_test_function():
        return "hello"

    @api_method("my_test_api")
    def my_new_test_function():
        return "world"

    assert "Overwriting existing API function 'my_test_api'" in caplog.text


def test_getattr_success(app_context):
    """Test AppAPI successfully dynamically looks up and invokes a registered API function."""

    @api_method("my_test_api")
    def my_test_function():
        return "hello"

    plugin_api = AppAPI("test_plugin", app_context)
    assert plugin_api.my_test_api() == "hello"


def test_getattr_fail(app_context):
    """Test AppAPI throws an AttributeError when invoking an unregistered function."""
    plugin_api = AppAPI("test_plugin", app_context)
    with pytest.raises(AttributeError):
        plugin_api.non_existent_api()


def test_list_available_apis(app_context):
    """Test AppAPI correctly describes the available registered API functions."""

    @api_method("my_test_api")
    def my_test_function(param1: str, param2: int = 5) -> str:
        """This is a test function."""
        return f"{param1}, {param2}"

    plugin_api = AppAPI("test_plugin", app_context)
    api_list = plugin_api.list_available_apis()

    assert len(api_list) == 1
    assert api_list[0]["name"] == "my_test_api"
    assert api_list[0]["docstring"] == "This is a test function."
    assert len(api_list[0]["parameters"]) == 2
    assert api_list[0]["parameters"][0]["name"] == "param1"
    assert api_list[0]["parameters"][1]["name"] == "param2"
    assert api_list[0]["parameters"][1]["default"] == 5


def test_listen_for_event(app_context, monkeypatch):
    """Test AppAPI properly bridges event listener registrations to the PluginManager."""
    mock_plugin_manager = MagicMock()
    # Mocking internal properties due to getter
    monkeypatch.setattr(app_context, "_plugin_manager", mock_plugin_manager)
    plugin_api = AppAPI("test_plugin", app_context)

    def my_callback():
        pass

    plugin_api.listen_for_event("my_event", my_callback)
    mock_plugin_manager.register_plugin_event_listener.assert_called_once_with(
        "my_event", my_callback, "test_plugin"
    )


def test_send_event(app_context, monkeypatch):
    """Test AppAPI properly bridges custom event triggers to the PluginManager."""
    mock_plugin_manager = MagicMock()
    monkeypatch.setattr(app_context, "_plugin_manager", mock_plugin_manager)
    plugin_api = AppAPI("test_plugin", app_context)

    plugin_api.send_event("my_event", 1, 2, key="value")
    mock_plugin_manager.trigger_custom_plugin_event.assert_called_once_with(
        "my_event", "test_plugin", 1, 2, key="value"
    )
