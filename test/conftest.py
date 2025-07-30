import pytest
import tempfile
import shutil
import os
import sys
from unittest.mock import MagicMock
from bedrock_server_manager.core.bedrock_server import BedrockServer

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
