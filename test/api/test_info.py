import pytest
from unittest.mock import patch, MagicMock

from bedrock_server_manager.api.info import (
    get_server_running_status,
    get_server_config_status,
    get_server_installed_version,
)
from bedrock_server_manager.error import BSMError


@pytest.fixture
def mock_get_server_instance(mocker, mock_bedrock_server):
    """Fixture to patch get_server_instance for the api.info module."""
    mock_bedrock_server.is_running.return_value = False
    mock_bedrock_server.get_status_from_config.return_value = "STOPPED"
    mock_bedrock_server.get_version.return_value = "1.0.0"
    return mocker.patch(
        "bedrock_server_manager.api.info.get_server_instance",
        return_value=mock_bedrock_server,
    )


class TestServerInfo:
    def test_get_server_running_status_running(self, real_bedrock_server):
        with patch.object(real_bedrock_server, "is_running", return_value=True):
            with patch(
                "bedrock_server_manager.api.info.get_server_instance",
                return_value=real_bedrock_server,
            ):
                result = get_server_running_status("test-server")
                assert result["status"] == "success"
                assert result["is_running"] is True

    def test_get_server_running_status_stopped(self, real_bedrock_server):
        with patch.object(real_bedrock_server, "is_running", return_value=False):
            with patch(
                "bedrock_server_manager.api.info.get_server_instance",
                return_value=real_bedrock_server,
            ):
                result = get_server_running_status("test-server")
                assert result["status"] == "success"
                assert result["is_running"] is False

    def test_get_server_config_status(self, real_bedrock_server):
        with patch(
            "bedrock_server_manager.api.info.get_server_instance",
            return_value=real_bedrock_server,
        ):
            # Set a status in the config
            real_bedrock_server.set_status_in_config("RUNNING")
            result = get_server_config_status("test-server")
            assert result["status"] == "success"
            assert result["config_status"] == "RUNNING"

    def test_get_server_installed_version(self, real_bedrock_server):
        with patch(
            "bedrock_server_manager.api.info.get_server_instance",
            return_value=real_bedrock_server,
        ):
            # Set a version in the config
            real_bedrock_server.set_version("1.2.3")
            result = get_server_installed_version("test-server")
            assert result["status"] == "success"
            assert result["installed_version"] == "1.2.3"

    def test_bsm_error_handling(self, real_bedrock_server):
        with patch.object(
            real_bedrock_server, "is_running", side_effect=BSMError("Test error")
        ):
            with patch(
                "bedrock_server_manager.api.info.get_server_instance",
                return_value=real_bedrock_server,
            ):
                result = get_server_running_status("test-server")
                assert result["status"] == "error"
                assert "Test error" in result["message"]
