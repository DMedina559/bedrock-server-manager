import pytest
import tempfile
import shutil
import os
import sys

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
