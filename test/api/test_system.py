import pytest
from unittest.mock import patch, MagicMock

from bedrock_server_manager.api.system import (
    get_bedrock_process_info,
    set_autoupdate,
)
from bedrock_server_manager.error import UserInputError


@pytest.fixture
def mock_get_server_instance(mocker, mock_bedrock_server):
    """Fixture to patch get_server_instance for the api.system module."""
    mock_bedrock_server.get_process_info.return_value = {"pid": 123}
    return mocker.patch(
        "bedrock_server_manager.api.system.get_server_instance",
        return_value=mock_bedrock_server,
    )


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
