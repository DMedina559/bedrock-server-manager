import pytest
from unittest.mock import patch, MagicMock

from bedrock_server_manager.api.info import (
    get_server_running_status,
    get_server_config_status,
    get_server_installed_version,
)
from bedrock_server_manager.error import BSMError


@pytest.fixture
def mock_bedrock_server():
    """Fixture for a mocked BedrockServer."""
    server = MagicMock()
    server.is_running.return_value = False
    server.get_status_from_config.return_value = "STOPPED"
    server.get_version.return_value = "1.0.0"
    return server


@pytest.fixture
def mock_get_server_instance(mock_bedrock_server):
    """Fixture to patch get_server_instance."""
    with patch(
        "bedrock_server_manager.api.info.get_server_instance",
        return_value=mock_bedrock_server,
    ) as mock:
        yield mock


class TestServerInfo:
    def test_get_server_running_status_running(
        self, mock_get_server_instance, mock_bedrock_server
    ):
        mock_bedrock_server.is_running.return_value = True
        result = get_server_running_status("test-server")
        assert result["status"] == "success"
        assert result["is_running"] is True

    def test_get_server_running_status_stopped(
        self, mock_get_server_instance, mock_bedrock_server
    ):
        result = get_server_running_status("test-server")
        assert result["status"] == "success"
        assert result["is_running"] is False

    def test_get_server_config_status(
        self, mock_get_server_instance, mock_bedrock_server
    ):
        result = get_server_config_status("test-server")
        assert result["status"] == "success"
        assert result["config_status"] == "STOPPED"

    def test_get_server_installed_version(
        self, mock_get_server_instance, mock_bedrock_server
    ):
        result = get_server_installed_version("test-server")
        assert result["status"] == "success"
        assert result["installed_version"] == "1.0.0"

    def test_bsm_error_handling(self, mock_get_server_instance, mock_bedrock_server):
        mock_bedrock_server.is_running.side_effect = BSMError("Test error")
        result = get_server_running_status("test-server")
        assert result["status"] == "error"
        assert "Test error" in result["message"]
