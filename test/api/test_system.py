import pytest
from unittest.mock import patch, MagicMock

from bedrock_server_manager.api.system import (
    get_bedrock_process_info,
    create_server_service,
    set_autoupdate,
    enable_server_service,
    disable_server_service,
)
from bedrock_server_manager.error import UserInputError


@pytest.fixture
def mock_bedrock_server():
    """Fixture for a mocked BedrockServer."""
    server = MagicMock()
    server.get_process_info.return_value = {"pid": 123}
    return server


@pytest.fixture
def mock_get_server_instance(mock_bedrock_server):
    """Fixture to patch get_server_instance."""
    with patch(
        "bedrock_server_manager.api.system.get_server_instance",
        return_value=mock_bedrock_server,
    ) as mock:
        yield mock


class TestSystemAPI:
    def test_get_bedrock_process_info_running(self, mock_get_server_instance):
        result = get_bedrock_process_info("test-server")
        assert result["status"] == "success"
        assert result["process_info"]["pid"] == 123

    def test_get_bedrock_process_info_not_running(
        self, mock_get_server_instance, mock_bedrock_server
    ):
        mock_bedrock_server.get_process_info.return_value = None
        result = get_bedrock_process_info("test-server")
        assert result["status"] == "success"
        assert result["process_info"] is None

    def test_set_autoupdate_true(self, mock_get_server_instance, mock_bedrock_server):
        result = set_autoupdate("test-server", "true")
        assert result["status"] == "success"
        mock_bedrock_server.set_autoupdate.assert_called_once_with(True)

    def test_set_autoupdate_false(self, mock_get_server_instance, mock_bedrock_server):
        result = set_autoupdate("test-server", "false")
        assert result["status"] == "success"
        mock_bedrock_server.set_autoupdate.assert_called_once_with(False)

    def test_set_autoupdate_invalid(self, mock_get_server_instance):
        with pytest.raises(UserInputError):
            set_autoupdate("test-server", "invalid")

    def test_create_server_service_autostart(
        self, mock_get_server_instance, mock_bedrock_server
    ):
        result = create_server_service("test-server", autostart=True)
        assert result["status"] == "success"
        mock_bedrock_server.create_service.assert_called_once()
        mock_bedrock_server.enable_service.assert_called_once()
        mock_bedrock_server.disable_service.assert_not_called()

    def test_create_server_service_no_autostart(
        self, mock_get_server_instance, mock_bedrock_server
    ):
        result = create_server_service("test-server", autostart=False)
        assert result["status"] == "success"
        mock_bedrock_server.create_service.assert_called_once()
        mock_bedrock_server.disable_service.assert_called_once()
        mock_bedrock_server.enable_service.assert_not_called()

    def test_enable_server_service(self, mock_get_server_instance, mock_bedrock_server):
        result = enable_server_service("test-server")
        assert result["status"] == "success"
        mock_bedrock_server.enable_service.assert_called_once()

    def test_disable_server_service(
        self, mock_get_server_instance, mock_bedrock_server
    ):
        result = disable_server_service("test-server")
        assert result["status"] == "success"
        mock_bedrock_server.disable_service.assert_called_once()
