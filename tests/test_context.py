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
    context = AppContext()
    context._db = db
    context.load()
    assert context.settings is not None


def test_app_context_reload(app_context, monkeypatch):
    """Test reload() clears caches and calls reload on sub-components."""
    settings_reload_mock = MagicMock()
    plugin_manager_reload_mock = MagicMock()

    monkeypatch.setattr(app_context.settings, "reload", settings_reload_mock)
    monkeypatch.setattr(
        app_context.plugin_manager, "reload", plugin_manager_reload_mock
    )

    # Set dummy cached values
    app_context._pre_app_config_cache = {"some": "config"}
    app_context._needs_setup = False
    app_context._config_dir = "/dummy/config"
    app_context._data_dir = "/dummy/data"
    app_context._db_url = "sqlite:///dummy.db"
    app_context._log_level = "DEBUG"
    app_context._log_dir = "/dummy/log"

    # Setup mocks for resource_monitor and log_streamer
    app_context._resource_monitor = MagicMock()
    app_context.log_streamer = MagicMock()

    app_context.reload()

    # Verify caches are cleared
    assert app_context._pre_app_config_cache is None
    assert app_context._needs_setup is None
    assert app_context._config_dir is None
    assert app_context._data_dir is None
    assert app_context._db_url is None
    assert app_context._log_level is None
    assert app_context._log_dir is None

    # Verify reload called
    settings_reload_mock.assert_called_once()
    plugin_manager_reload_mock.assert_called_once()

    # Verify monitors are stopped and started
    app_context._resource_monitor.stop.assert_called_once()
    app_context._resource_monitor.start.assert_called_once()
    app_context.log_streamer.stop.assert_called_once()
    app_context.log_streamer.start.assert_called_once()


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
