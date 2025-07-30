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


@pytest.fixture(autouse=True)
def isolated_settings():
    """
    This fixture creates a temporary data directory and sets the
    BEDROCK_SERVER_MANAGER_DATA_DIR environment variable to point to it.
    This isolates the tests from the user's actual data and configuration.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        original_value = os.environ.get("BEDROCK_SERVER_MANAGER_DATA_DIR")
        os.environ["BEDROCK_SERVER_MANAGER_DATA_DIR"] = tmpdir
        yield
        if original_value is None:
            del os.environ["BEDROCK_SERVER_MANAGER_DATA_DIR"]
        else:
            os.environ["BEDROCK_SERVER_MANAGER_DATA_DIR"] = original_value


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
