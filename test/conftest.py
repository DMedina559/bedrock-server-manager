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
