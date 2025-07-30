import pytest
from unittest.mock import patch, MagicMock

from bedrock_server_manager.api.utils import (
    validate_server_exist,
    validate_server_name_format,
    update_server_statuses,
    get_system_and_app_info,
    server_lifecycle_manager,
)
from bedrock_server_manager.error import BSMError, ServerStartError


@pytest.fixture
def mock_get_server_instance(mocker, mock_bedrock_server):
    """Fixture to patch get_server_instance for the api.utils module."""
    mock_bedrock_server.is_installed.return_value = True
    mock_bedrock_server.is_running.return_value = False
    return mocker.patch(
        "bedrock_server_manager.api.utils.get_server_instance",
        return_value=mock_bedrock_server,
    )


class TestServerValidation:
    def test_validate_server_exist_success(self, mock_get_server_instance):
        result = validate_server_exist("test-server")
        assert result["status"] == "success"

    def test_validate_server_exist_not_installed(
        self, mock_get_server_instance, mock_bedrock_server
    ):
        mock_bedrock_server.is_installed.return_value = False
        result = validate_server_exist("test-server")
        assert result["status"] == "error"
        assert "not installed" in result["message"]

    def test_validate_server_name_format_success(self):
        result = validate_server_name_format("valid-name")
        assert result["status"] == "success"

    def test_validate_server_name_format_invalid(self):
        result = validate_server_name_format("invalid name!")
        assert result["status"] == "error"


class TestStatusAndUpdate:
    def test_update_server_statuses(self, mocker):
        mock_manager = MagicMock()
        mock_manager.get_servers_data.return_value = (
            [{"name": "server1"}, {"name": "server2"}],
            [],
        )
        mocker.patch(
            "bedrock_server_manager.api.utils.get_manager_instance",
            return_value=mock_manager,
        )
        result = update_server_statuses()
        assert result["status"] == "success"
        assert "2 servers" in result["message"]

    def test_get_system_and_app_info(self, mocker):
        mock_manager = MagicMock()
        mock_manager.get_os_type.return_value = "Linux"
        mock_manager.get_app_version.return_value = "1.0.0"
        mocker.patch(
            "bedrock_server_manager.api.utils.get_manager_instance",
            return_value=mock_manager,
        )
        result = get_system_and_app_info()
        assert result["status"] == "success"
        assert result["data"]["os_type"] == "Linux"
        assert result["data"]["app_version"] == "1.0.0"


class TestServerLifecycleManager:
    @patch("bedrock_server_manager.api.utils.api_stop_server")
    @patch("bedrock_server_manager.api.utils.api_start_server")
    def test_lifecycle_manager_stop_and_restart(
        self, mock_start, mock_stop, mock_get_server_instance, mock_bedrock_server
    ):
        mock_bedrock_server.is_running.return_value = True
        mock_stop.return_value = {"status": "success"}
        mock_start.return_value = {"status": "success"}

        with server_lifecycle_manager("test-server", stop_before=True):
            pass

        mock_stop.assert_called_once_with("test-server")
        mock_start.assert_called_once_with("test-server", mode="detached")

    @patch("bedrock_server_manager.api.utils.api_stop_server")
    @patch("bedrock_server_manager.api.utils.api_start_server")
    def test_lifecycle_manager_exception(
        self, mock_start, mock_stop, mock_get_server_instance, mock_bedrock_server
    ):
        mock_bedrock_server.is_running.return_value = True
        mock_stop.return_value = {"status": "success"}
        mock_start.return_value = {"status": "success"}

        with pytest.raises(ValueError):
            with server_lifecycle_manager("test-server", stop_before=True):
                raise ValueError("Test exception")

        mock_stop.assert_called_once_with("test-server")
        mock_start.assert_called_once_with("test-server", mode="detached")

    @patch("bedrock_server_manager.api.utils.api_stop_server")
    @patch("bedrock_server_manager.api.utils.api_start_server")
    def test_lifecycle_manager_restart_on_success_only(
        self, mock_start, mock_stop, mock_get_server_instance, mock_bedrock_server
    ):
        mock_bedrock_server.is_running.return_value = True
        mock_stop.return_value = {"status": "success"}

        with pytest.raises(ValueError):
            with server_lifecycle_manager(
                "test-server", stop_before=True, restart_on_success_only=True
            ):
                raise ValueError("Test exception")

        mock_stop.assert_called_once_with("test-server")
        mock_start.assert_not_called()
