from unittest.mock import MagicMock

from bedrock_server_manager.api.application import (
    get_all_servers_data,
    get_system_and_app_info,
    list_available_worlds_api,
    update_server_statuses,
)
from bedrock_server_manager.error import BSMError, FileError


def test_list_available_worlds_api_success(app_context, monkeypatch):
    """Test list_available_worlds_api properly routes request and formats response."""
    monkeypatch.setattr(
        "bedrock_server_manager.api.application.list_content_files",
        MagicMock(return_value=["/world1.mcworld"]),
    )

    result = list_available_worlds_api(app_context)

    assert result["status"] == "success"
    assert result["files"] == ["/world1.mcworld"]


def test_list_available_worlds_api_error(app_context, monkeypatch):
    """Test list_available_worlds_api handles FileError safely."""
    monkeypatch.setattr(
        "bedrock_server_manager.api.application.list_content_files",
        MagicMock(side_effect=FileError("No dir")),
    )

    result = list_available_worlds_api(app_context)

    assert result["status"] == "error"
    assert "No dir" in result["message"]


def test_get_all_servers_data_success(app_context, monkeypatch):
    """Test get_all_servers_data formats success dictionary correctly."""
    mock_get = MagicMock(return_value=([{"name": "srv1"}], []))
    monkeypatch.setattr(
        "bedrock_server_manager.utils.server.get_servers_data", mock_get
    )

    result = get_all_servers_data(app_context)

    assert result["status"] == "success"
    assert result["servers"][0]["name"] == "srv1"


def test_get_all_servers_data_partial_errors(app_context, monkeypatch):
    """Test get_all_servers_data includes partial error arrays in message string."""
    mock_get = MagicMock(return_value=([{"name": "srv1"}], ["Error reading srv2"]))
    monkeypatch.setattr(
        "bedrock_server_manager.utils.server.get_servers_data", mock_get
    )

    result = get_all_servers_data(app_context)
    assert result["status"] == "success"
    assert "Error reading srv2" in result["message"]
    assert len(result["servers"]) == 1


def test_get_all_servers_data_bsm_error(app_context, monkeypatch):
    """Test get_all_servers_data correctly wraps full BSMError throws."""
    mock_get = MagicMock(side_effect=BSMError("Base directory gone"))
    monkeypatch.setattr(
        "bedrock_server_manager.utils.server.get_servers_data", mock_get
    )

    result = get_all_servers_data(app_context)
    assert result["status"] == "error"
    assert "Base directory gone" in result["message"]


def test_get_system_and_app_info_success(app_context, monkeypatch):
    """Test get_system_and_app_info correctly builds response payload."""
    monkeypatch.setattr("platform.system", lambda: "Linux")

    result = get_system_and_app_info(app_context)

    assert result["status"] == "success"
    assert result["os_type"] == "Linux"
    assert "app_version" in result
    assert "splash_text" in result


def test_get_system_and_app_info_error(app_context, monkeypatch):
    """Test get_system_and_app_info handles platform failure gracefully."""

    def mock_fail():
        raise Exception("Platform failure")

    monkeypatch.setattr("platform.system", mock_fail)

    result = get_system_and_app_info(app_context)
    assert result["status"] == "error"


def test_update_server_statuses_success(app_context, monkeypatch):
    """Test update_server_statuses handles core responses and formats messages properly."""
    mock_get = MagicMock(return_value=([{"name": "srv1"}], []))
    monkeypatch.setattr(
        "bedrock_server_manager.utils.server.get_servers_data", mock_get
    )

    result = update_server_statuses(app_context)

    assert result["status"] == "success"
    assert result["message"] == "Status check completed for 1 servers."


def test_update_server_statuses_with_errors(app_context, monkeypatch):
    """Test update_server_statuses handles core responses returning partial failure cleanly."""
    mock_get = MagicMock(return_value=([{"name": "srv1"}], ["Error on srv2"]))
    monkeypatch.setattr(
        "bedrock_server_manager.utils.server.get_servers_data", mock_get
    )

    result = update_server_statuses(app_context)

    assert result["status"] == "error"
    assert "Completed with errors" in result["message"]
    assert result["updated_servers_count"] == 1


def test_update_server_statuses_bsm_error(app_context, monkeypatch):
    """Test update_server_statuses catches base discovery BSMError calls."""
    mock_get = MagicMock(side_effect=BSMError("App issue"))
    monkeypatch.setattr(
        "bedrock_server_manager.utils.server.get_servers_data", mock_get
    )

    result = update_server_statuses(app_context)
    assert result["status"] == "error"
    assert "Error accessing directories" in result["message"]
