import pytest
import tempfile
import shutil
import os
import sys
from unittest.mock import MagicMock

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
