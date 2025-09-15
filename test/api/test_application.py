import pytest
from unittest.mock import patch, MagicMock

from bedrock_server_manager.api.application import (
    get_application_info_api,
    list_available_worlds_api,
    list_available_addons_api,
    get_all_servers_data,
)
from bedrock_server_manager.error import FileError, BSMError


class TestApplicationInfo:
    def test_get_application_info_api(self, app_context):
        result = get_application_info_api(app_context=app_context)
        assert result["status"] == "success"
        assert result["data"]["application_name"] == "Bedrock Server Manager"


class TestContentListing:
    def test_list_available_worlds_api(self, app_context, tmp_path):
        worlds_dir = tmp_path / "content" / "worlds"
        worlds_dir.mkdir(parents=True, exist_ok=True)
        (worlds_dir / "world1.mcworld").touch()
        app_context.manager._content_dir = str(tmp_path / "content")

        result = list_available_worlds_api(app_context=app_context)
        assert result["status"] == "success"
        assert len(result["files"]) == 1
        assert "world1.mcworld" in result["files"][0]

    def test_list_available_addons_api(self, app_context, tmp_path):
        addons_dir = tmp_path / "content" / "addons"
        addons_dir.mkdir(parents=True, exist_ok=True)
        (addons_dir / "addon1.mcpack").touch()
        app_context.manager._content_dir = str(tmp_path / "content")

        result = list_available_addons_api(app_context=app_context)
        assert result["status"] == "success"
        assert len(result["files"]) == 1
        assert "addon1.mcpack" in result["files"][0]

    def test_list_available_worlds_api_file_error(self, app_context):
        with patch.object(
            app_context.manager,
            "list_available_worlds",
            side_effect=FileError("Test error"),
        ):
            result = list_available_worlds_api(app_context=app_context)
            assert result["status"] == "error"
            assert "Test error" in result["message"]

    def test_list_available_addons_api_file_error(self, app_context):
        with patch.object(
            app_context.manager,
            "list_available_addons",
            side_effect=FileError("Test error"),
        ):
            result = list_available_addons_api(app_context=app_context)
            assert result["status"] == "error"
            assert "Test error" in result["message"]


class TestGetAllServersData:
    def test_get_all_servers_data_success(self, app_context, real_bedrock_server):
        result = get_all_servers_data(app_context=app_context)
        assert result["status"] == "success"
        assert len(result["servers"]) == 1

    def test_get_all_servers_data_partial_success(self, app_context):
        with patch.object(
            app_context.manager,
            "get_servers_data",
            return_value=([{"name": "server1"}], ["Error on server2"]),
        ):
            result = get_all_servers_data(app_context=app_context)
            assert result["status"] == "success"
            assert len(result["servers"]) == 1
            assert "Completed with errors" in result["message"]

    def test_get_all_servers_data_bsm_error(self, app_context):
        with patch.object(
            app_context.manager,
            "get_servers_data",
            side_effect=BSMError("Test BSM error"),
        ):
            result = get_all_servers_data(app_context=app_context)
            assert result["status"] == "error"
            assert "Test BSM error" in result["message"]
