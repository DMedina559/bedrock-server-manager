import pytest
from unittest.mock import patch, MagicMock

from bedrock_server_manager.api.application import (
    get_application_info_api,
    list_available_worlds_api,
    list_available_addons_api,
    get_all_servers_data,
)
from bedrock_server_manager.error import FileError, BSMError


@pytest.fixture
def mock_manager():
    """Fixture for a mocked BedrockServerManager."""
    manager = MagicMock()
    manager._app_name_title = "Bedrock Server Manager"
    manager.get_app_version.return_value = "1.0.0"
    manager.get_os_type.return_value = "Linux"
    manager._base_dir = "/servers"
    manager._content_dir = "/content"
    manager._config_dir = "/config"
    manager.list_available_worlds.return_value = ["/content/worlds/world1.mcworld"]
    manager.list_available_addons.return_value = ["/content/addons/addon1.mcpack"]
    manager.get_servers_data.return_value = ([], [])
    return manager


@pytest.fixture
def mock_get_manager_instance(mock_manager):
    """Fixture to patch get_manager_instance."""
    with patch(
        "bedrock_server_manager.api.application.get_manager_instance",
        return_value=mock_manager,
    ) as mock:
        yield mock


class TestApplicationInfo:
    def test_get_application_info_api(self, mock_get_manager_instance):
        result = get_application_info_api()
        assert result["status"] == "success"
        assert result["data"]["application_name"] == "Bedrock Server Manager"
        assert result["data"]["version"] == "1.0.0"


class TestContentListing:
    def test_list_available_worlds_api(self, mock_get_manager_instance):
        result = list_available_worlds_api()
        assert result["status"] == "success"
        assert result["files"] == ["/content/worlds/world1.mcworld"]

    def test_list_available_addons_api(self, mock_get_manager_instance):
        result = list_available_addons_api()
        assert result["status"] == "success"
        assert result["files"] == ["/content/addons/addon1.mcpack"]

    def test_list_available_worlds_api_file_error(
        self, mock_get_manager_instance, mock_manager
    ):
        mock_manager.list_available_worlds.side_effect = FileError("Test error")
        result = list_available_worlds_api()
        assert result["status"] == "error"
        assert "Test error" in result["message"]

    def test_list_available_addons_api_file_error(
        self, mock_get_manager_instance, mock_manager
    ):
        mock_manager.list_available_addons.side_effect = FileError("Test error")
        result = list_available_addons_api()
        assert result["status"] == "error"
        assert "Test error" in result["message"]


class TestGetAllServersData:
    def test_get_all_servers_data_success(
        self, mock_get_manager_instance, mock_manager
    ):
        mock_manager.get_servers_data.return_value = ([{"name": "server1"}], [])
        result = get_all_servers_data()
        assert result["status"] == "success"
        assert len(result["servers"]) == 1

    def test_get_all_servers_data_partial_success(
        self, mock_get_manager_instance, mock_manager
    ):
        mock_manager.get_servers_data.return_value = (
            [{"name": "server1"}],
            ["Error on server2"],
        )
        result = get_all_servers_data()
        assert result["status"] == "success"
        assert len(result["servers"]) == 1
        assert "Completed with errors" in result["message"]

    def test_get_all_servers_data_bsm_error(
        self, mock_get_manager_instance, mock_manager
    ):
        mock_manager.get_servers_data.side_effect = BSMError("Test BSM error")
        result = get_all_servers_data()
        assert result["status"] == "error"
        assert "Test BSM error" in result["message"]
