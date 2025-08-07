import pytest
import tempfile
import shutil
import os
import sys
from unittest.mock import MagicMock
from bedrock_server_manager.core.bedrock_server import BedrockServer
from bedrock_server_manager.core.manager import BedrockServerManager

# Add the src directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))


from appdirs import user_config_dir


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch, tmp_path):
    """
    This fixture creates a temporary data and config directory and mocks
    appdirs.user_config_dir to ensure all configuration and data files
    are isolated to the temporary location for the duration of the test.
    """
    # Create a temporary directory for the app's data
    test_data_dir = tmp_path / "test_data"
    test_data_dir.mkdir()

    # Create a temporary directory for the app's config files
    test_config_dir = tmp_path / "test_config"
    test_config_dir.mkdir()

    # Mock the user_config_dir function to return our temporary config directory
    monkeypatch.setattr(
        "appdirs.user_config_dir", lambda *args, **kwargs: str(test_config_dir)
    )

    # We also need to set the `data_dir` in the mocked config file
    # for the `Settings` class to find it.
    config_file = test_config_dir / "bedrock_server_manager.json"
    config_data = {"data_dir": str(test_data_dir)}
    with open(config_file, "w") as f:
        import json

        json.dump(config_data, f)

    # The `Settings` class also checks the BSM_DATA_DIR environment variable
    # as a fallback. It's a good practice to mock this as well to be explicit
    # about test isolation, even though the primary path is now mocked.
    monkeypatch.setenv("BSM_DATA_DIR", str(test_data_dir))

    # Reload the bcm_config module to ensure the new mocked paths are used
    import bedrock_server_manager.config.bcm_config as bcm_config
    import importlib

    importlib.reload(bcm_config)

    yield

    # Teardown: Remove the mocked environment variable
    monkeypatch.delenv("BSM_DATA_DIR")
    # Reset the bcm_config module to its original state
    importlib.reload(bcm_config)


@pytest.fixture
def mock_get_settings_instance(monkeypatch):
    """Fixture to patch get_settings_instance."""
    mock = MagicMock()
    monkeypatch.setattr(
        "bedrock_server_manager.instances.get_settings_instance", lambda: mock
    )
    return mock


@pytest.fixture
def mock_settings(mocker):
    """Fixture for a mocked Settings object."""
    settings = MagicMock()
    settings.get.return_value = "/tmp"
    settings.config_dir = "/tmp/config"
    return settings


@pytest.fixture
def mock_bedrock_server(tmp_path):
    """Fixture for a mocked BedrockServer."""
    # Create a mock object with the same interface as BedrockServer
    server = MagicMock(spec=BedrockServer)

    # Set default attributes for the mock
    server.server_name = "test_server"
    server.server_dir = str(tmp_path / "test_server")
    server.server_config_dir = str(tmp_path / "test_server_config")
    server.is_running.return_value = False
    server.get_status.return_value = "STOPPED"
    server.get_version.return_value = "1.20.0"

    return server


@pytest.fixture
def mock_get_server_instance(mocker, mock_bedrock_server):
    """Fixture to patch get_server_instance to return a consistent mock BedrockServer."""
    return mocker.patch(
        "bedrock_server_manager.instances.get_server_instance",
        return_value=mock_bedrock_server,
        autospec=True,
    )


@pytest.fixture
def mock_bedrock_server_manager(mocker):
    """Fixture for a mocked BedrockServerManager."""
    # Create a mock object with the same interface as BedrockServerManager
    manager = MagicMock(spec=BedrockServerManager)

    # Set default attributes for the mock
    manager._app_name_title = "Bedrock Server Manager"
    manager.get_app_version.return_value = "1.0.0"
    manager.get_os_type.return_value = "Linux"
    manager._base_dir = "/servers"
    manager._content_dir = "/content"
    manager._config_dir = "/config"
    manager.list_available_worlds.return_value = ["/content/worlds/world1.mcworld"]
    manager.list_available_addons.return_value = ["/content/addons/addon1.mcpack"]
    manager.get_servers_data.return_value = ([], [])
    manager.can_manage_services = True

    return manager


@pytest.fixture
def mock_get_manager_instance(mocker, mock_bedrock_server_manager):
    """Fixture to patch get_manager_instance to return a consistent mock BedrockServerManager."""
    return mocker.patch(
        "bedrock_server_manager.instances.get_manager_instance",
        return_value=mock_bedrock_server_manager,
        autospec=True,
    )


@pytest.fixture
def temp_file(tmp_path):
    """Creates a temporary file for tests."""
    file = tmp_path / "temp_file"
    file.touch()
    return str(file)


@pytest.fixture
def temp_dir(tmp_path):
    """Creates a temporary directory for tests."""
    return str(tmp_path)


@pytest.fixture
def mock_db_session_manager(mocker):
    def _mock_db_session_manager(db_session):
        mock_session_manager = mocker.MagicMock()
        mock_session_manager.return_value.__enter__.return_value = db_session
        return mock_session_manager

    return _mock_db_session_manager


@pytest.fixture(autouse=True)
def db_session():
    """
    Fixture to set up and tear down the database for each test.
    This ensures that each test runs in a clean, isolated environment.
    """
    from bedrock_server_manager.db import database

    # Setup: initialize the database with a test-specific URL
    database.initialize_database("sqlite://")
    yield
    # Teardown: reset the database module's state
    database.engine = None
    database.SessionLocal = None
    database._TABLES_CREATED = False


@pytest.fixture(autouse=True)
def reset_settings_singleton():
    """Fixture to reset the Settings singleton before each test."""
    from bedrock_server_manager.config import settings

    settings.Settings._instance = None
    yield
    settings.Settings._instance = None


@pytest.fixture
def real_bedrock_server(isolated_settings):
    """Fixture for a real BedrockServer instance."""
    from bedrock_server_manager.config.settings import Settings
    import os

    settings = Settings()
    app_data_dir = settings.app_data_dir
    config_dir = settings.config_dir

    print(f"app_data_dir: {app_data_dir}")
    print(f"config_dir: {config_dir}")

    server_name = "test_server"

    # Create the server's main directory
    server_dir = os.path.join(app_data_dir, "servers", server_name)
    os.makedirs(server_dir, exist_ok=True)
    print(f"server_dir: {server_dir}, exists: {os.path.exists(server_dir)}")

    # Create the server-specific config directory
    server_config_dir = os.path.join(config_dir, server_name)
    os.makedirs(server_config_dir, exist_ok=True)
    print(
        f"server_config_dir: {server_config_dir}, exists: {os.path.exists(server_config_dir)}"
    )

    properties_file = os.path.join(server_dir, "server.properties")
    with open(properties_file, "w") as f:
        f.write("server-name=test-server\nmax-players=5\nlevel-name=world\n")

    import platform

    # Create a dummy executable
    executable_name = "bedrock_server"
    if platform.system() == "Windows":
        executable_name += ".exe"
    executable_path = os.path.join(server_dir, executable_name)
    with open(executable_path, "w") as f:
        f.write(
            """#!/bin/bash
while read line; do
  if [[ "$line" == "stop" ]]; then
    exit 0
  fi
done
"""
        )
    os.chmod(executable_path, 0o755)

    server = BedrockServer(server_name, settings_instance=settings)
    return server


@pytest.fixture
def real_manager(tmp_path):
    """Fixture for a real BedrockServerManager instance."""
    from bedrock_server_manager.core.manager import BedrockServerManager
    from bedrock_server_manager.config.settings import Settings
    from unittest.mock import patch

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    config_dir = data_dir / ".config"
    config_dir.mkdir()
    servers_dir = data_dir / "servers"
    servers_dir.mkdir()
    content_dir = data_dir / "content"
    content_dir.mkdir()

    with patch("appdirs.user_config_dir", return_value=str(config_dir)):
        with patch(
            "bedrock_server_manager.config.bcm_config.load_config",
            return_value={"data_dir": str(data_dir)},
        ):
            settings = Settings()
            manager = BedrockServerManager(settings)
            # Create a dummy web ui pid file
            web_ui_pid_path = manager.get_web_ui_pid_path()
            with open(web_ui_pid_path, "w") as f:
                f.write("12345")
            return manager


@pytest.fixture
def real_plugin_manager(tmp_path):
    """Fixture for a real PluginManager instance."""
    from bedrock_server_manager.plugins.plugin_manager import PluginManager
    from bedrock_server_manager.config.settings import Settings
    from unittest.mock import patch

    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir()
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    # Create a dummy plugin
    plugin1_dir = plugins_dir / "plugin1"
    plugin1_dir.mkdir()
    with open(plugin1_dir / "__init__.py", "w") as f:
        f.write(
            """
from bedrock_server_manager.plugins.plugin_base import PluginBase

class Plugin(PluginBase):
    version = "1.0"
    def on_load(self):
        pass
"""
        )

    with patch("appdirs.user_config_dir", return_value=str(config_dir)):
        settings = Settings()
        settings.set("paths.plugins", str(plugins_dir))
        manager = PluginManager(settings)
        manager.plugin_dirs = [plugins_dir]
        manager.load_plugins()
        return manager
