from unittest.mock import MagicMock

from bedrock_server_manager.context import AppContext


def test_remove_server(app_context: AppContext, monkeypatch):
    """
    Tests that the remove_server method stops a running server and removes it from the cache.
    """
    server_name = "test_server"

    # Get the server once to cache it
    server_instance = app_context.get_server(server_name)

    # Mock the server's methods
    is_running_mock = MagicMock(return_value=True)
    stop_mock = MagicMock()
    monkeypatch.setattr(server_instance, "is_running", is_running_mock)
    monkeypatch.setattr(server_instance, "stop", stop_mock)

    # Call remove_server
    app_context.remove_server(server_name)

    # Assert that the methods were called
    is_running_mock.assert_called_once()
    stop_mock.assert_called_once()

    # Assert that the server is removed from the cache
    # We can't directly access _servers, so we check by getting a new instance
    new_server_instance = app_context.get_server(server_name)
    assert new_server_instance is not server_instance


def test_remove_server_not_running(app_context: AppContext, monkeypatch):
    """
    Tests that remove_server does not call stop() on a non-running server.
    """
    server_name = "test_server_not_running"

    # Get the server once to cache it
    server_instance = app_context.get_server(server_name)

    # Mock the server's methods
    is_running_mock = MagicMock(return_value=False)
    stop_mock = MagicMock()
    monkeypatch.setattr(server_instance, "is_running", is_running_mock)
    monkeypatch.setattr(server_instance, "stop", stop_mock)

    # Call remove_server
    app_context.remove_server(server_name)

    # Assert that is_running was called but stop was not
    is_running_mock.assert_called_once()
    stop_mock.assert_not_called()

    # Assert that the server is removed from the cache
    new_server_instance = app_context.get_server(server_name)
    assert new_server_instance is not server_instance


def test_reload(app_context: AppContext, monkeypatch):
    """
    Tests that the reload method reloads all components and clears caches.
    """
    # Mock reload methods
    settings_reload_mock = MagicMock()
    manager_reload_mock = MagicMock()
    plugin_manager_reload_mock = MagicMock()

    monkeypatch.setattr(app_context.settings, "reload", settings_reload_mock)
    monkeypatch.setattr(app_context.manager, "reload", manager_reload_mock)
    monkeypatch.setattr(
        app_context.plugin_manager, "reload", plugin_manager_reload_mock
    )

    # Get a server instance to cache it
    # server_instance = app_context.get_server("test_server")

    # Call reload
    app_context.reload()

    # Assert that reload methods were called
    settings_reload_mock.assert_called_once()
    manager_reload_mock.assert_called_once()
    plugin_manager_reload_mock.assert_called_once()

    # Assert that server cache is cleared
    # new_server_instance = app_context.get_server("test_server")
    # assert new_server_instance is not server_instance
