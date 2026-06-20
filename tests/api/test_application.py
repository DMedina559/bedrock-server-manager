from unittest.mock import patch

from bedrock_server_manager.api.application import (
    get_all_servers_data,
    list_available_worlds_api,
)
from bedrock_server_manager.error import BSMError, FileError


def test_list_available_worlds_api(app_context, tmp_path):
    worlds_dir = tmp_path / "content" / "worlds"
    worlds_dir.mkdir(parents=True, exist_ok=True)
    (worlds_dir / "world1.mcworld").touch()
    app_context.settings.set("paths.content", str(tmp_path / "content"))

    result = list_available_worlds_api(app_context=app_context)
    assert result["status"] == "success"
    assert len(result["files"]) == 1
    assert "world1.mcworld" in result["files"][0]


def test_list_available_worlds_api_file_error(app_context):
    with patch(
        "bedrock_server_manager.api.application.list_content_files",
        side_effect=FileError("Test error"),
    ):
        result = list_available_worlds_api(app_context=app_context)
        assert result["status"] == "error"
        assert "Test error" in result["message"]


def test_get_all_servers_data_success(app_context, real_bedrock_server):
    result = get_all_servers_data(app_context=app_context)
    assert result["status"] == "success"
    assert len(result["servers"]) == 1


def test_get_all_servers_data_partial_success(app_context):
    with patch(
        "bedrock_server_manager.utils.server.get_servers_data",
        return_value=([{"name": "server1"}], ["Error on server2"]),
    ):
        result = get_all_servers_data(app_context=app_context)
        assert result["status"] == "success"
        assert len(result["servers"]) == 1
        assert "Completed with errors" in result["message"]


def test_get_all_servers_data_bsm_error(app_context):
    with patch(
        "bedrock_server_manager.utils.server.get_servers_data",
        side_effect=BSMError("Test BSM error"),
    ):
        result = get_all_servers_data(app_context=app_context)
        assert result["status"] == "error"
        assert "Test BSM error" in result["message"]


class TestStatusAndUpdate:
    def test_update_server_statuses(self, app_context):
        from unittest.mock import patch

        from bedrock_server_manager.api.application import update_server_statuses

        with patch(
            "bedrock_server_manager.utils.server.get_servers_data",
            return_value=([{"name": "server1"}, {"name": "server2"}], []),
        ):
            result = update_server_statuses(app_context=app_context)
            assert result["status"] == "success"
            assert "2 servers" in result["message"]

    def test_get_system_and_app_info(self, app_context):
        from unittest.mock import patch

        from bedrock_server_manager.api.application import get_system_and_app_info

        app_context.splash_txt = "Hello World"
        with patch("platform.system", return_value="Linux"):
            with patch(
                "bedrock_server_manager.api.application.config_const.get_installed_version",
                return_value="1.0.0",
            ):
                result = get_system_and_app_info(app_context=app_context)
                assert result["status"] == "success"
                assert result["os_type"] == "Linux"
                assert result["app_version"] == "1.0.0"
