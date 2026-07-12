from unittest.mock import MagicMock

from bedrock_server_manager.context import AppContext
from bedrock_server_manager.core.bedrock_server import BedrockServer


def test_app_context_initialization(app_context):
    """Test that AppContext initializes correctly and properties are lazily loaded."""
    assert app_context._settings is not None
    assert app_context._db is not None
    assert app_context._api is None  # Should be loaded lazily
    assert app_context._plugin_manager is not None  # initialized in fixture
    assert app_context._task_manager is None

    # Access lazy loaded properties
    api = app_context.api
    assert api is not None
    assert app_context._api is api

    task_manager = app_context.task_manager
    assert task_manager is not None
    assert app_context._task_manager is task_manager


def test_app_context_load_without_prior_settings(db, isolated_bcm_config):
    """Test load() creates settings if not provided."""
    context = AppContext(db=db)
    context.load()
    assert context.settings is not None


def test_app_context_reload(app_context, monkeypatch):
    """Test reload() calls reload on sub-components."""
    settings_reload_mock = MagicMock()
    plugin_manager_reload_mock = MagicMock()

    monkeypatch.setattr(app_context.settings, "reload", settings_reload_mock)
    monkeypatch.setattr(
        app_context.plugin_manager, "reload", plugin_manager_reload_mock
    )

    app_context.reload()

    settings_reload_mock.assert_called_once()
    plugin_manager_reload_mock.assert_called_once()


def test_get_server_creates_and_caches(app_context):
    """Test get_server creates a new server instance and caches it."""
    server_name = "test_server_1"
    assert server_name not in app_context._servers

    server1 = app_context.get_server(server_name)
    assert isinstance(server1, BedrockServer)
    assert server_name in app_context._servers

    # Get again, should return cached instance
    server2 = app_context.get_server(server_name)
    assert server1 is server2


def test_remove_server_running(app_context, monkeypatch):
    """Test remove_server stops a running server and removes it from cache."""
    server_name = "test_server_to_remove"
    server = app_context.get_server(server_name)

    is_running_mock = MagicMock(return_value=True)
    stop_mock = MagicMock()

    monkeypatch.setattr(server, "is_running", is_running_mock)
    monkeypatch.setattr(server, "stop", stop_mock)

    app_context.remove_server(server_name)

    is_running_mock.assert_called_once()
    stop_mock.assert_called_once()
    assert server_name not in app_context._servers


def test_remove_server_not_running(app_context, monkeypatch):
    """Test remove_server removes a stopped server from cache without stopping it."""
    server_name = "test_server_stopped"
    server = app_context.get_server(server_name)

    is_running_mock = MagicMock(return_value=False)
    stop_mock = MagicMock()

    monkeypatch.setattr(server, "is_running", is_running_mock)
    monkeypatch.setattr(server, "stop", stop_mock)

    app_context.remove_server(server_name)

    is_running_mock.assert_called_once()
    stop_mock.assert_not_called()
    assert server_name not in app_context._servers


def test_remove_server_non_existent(app_context):
    """Test remove_server handles non-existent servers gracefully."""
    # Should not raise an error
    app_context.remove_server("does_not_exist")


def test_stop_all_servers(app_context, monkeypatch):
    """Test stop_all_servers stops all running cached servers."""
    server1 = app_context.get_server("server1")
    server2 = app_context.get_server("server2")

    mock_api = MagicMock()
    monkeypatch.setattr(app_context, "_api", mock_api)

    monkeypatch.setattr(server1, "is_running", MagicMock(return_value=True))
    monkeypatch.setattr(server2, "is_running", MagicMock(return_value=False))

    app_context.stop_all_servers()

    mock_api.stop_server.assert_called_once_with("server1")


def test_stop_all_servers_no_api(app_context, monkeypatch):
    """Test stop_all_servers stops servers directly if API is not loaded."""
    server1 = app_context.get_server("server1")

    # Ensure api is not loaded
    if hasattr(app_context, "_api"):
        delattr(app_context, "_api")

    monkeypatch.setattr(server1, "is_running", MagicMock(return_value=True))
    mock_stop = MagicMock()
    monkeypatch.setattr(server1, "stop", mock_stop)

    app_context.stop_all_servers()

    mock_stop.assert_called_once()
