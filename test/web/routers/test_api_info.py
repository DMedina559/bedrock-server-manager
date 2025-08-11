from unittest.mock import patch, MagicMock
import pytest


@patch("bedrock_server_manager.web.routers.api_info.info_api.get_server_running_status")
def test_get_server_running_status_api_route_success(
    mock_get_status, authenticated_client
):
    """Test the get_server_running_status_api_route with a successful status."""
    app_context = MagicMock()
    authenticated_client.app.state.app_context = app_context
    mock_get_status.return_value = {"status": "success", "running": True}
    response = authenticated_client.get("/api/server/test-server/status")
    assert response.status_code == 200
    assert response.json()["data"]["running"] is True
    mock_get_status.assert_called_once_with(
        server_name="test-server", app_context=app_context
    )


@patch("bedrock_server_manager.web.routers.api_info.info_api.get_server_running_status")
def test_get_server_running_status_api_route_failure(
    mock_get_status, authenticated_client
):
    """Test the get_server_running_status_api_route with a failed status."""
    app_context = MagicMock()
    authenticated_client.app.state.app_context = app_context
    mock_get_status.return_value = {
        "status": "error",
        "message": "Failed to get status",
    }
    response = authenticated_client.get("/api/server/test-server/status")
    assert response.status_code == 500
    assert "Unexpected error checking running status." in response.json()["detail"]


@patch("bedrock_server_manager.web.routers.api_info.info_api.get_server_config_status")
def test_get_server_config_status_api_route_success(
    mock_get_status, authenticated_client
):
    """Test the get_server_config_status_api_route with a successful status."""
    app_context = MagicMock()
    authenticated_client.app.state.app_context = app_context
    mock_get_status.return_value = {"status": "success", "config_status": "RUNNING"}
    response = authenticated_client.get("/api/server/test-server/config_status")
    assert response.status_code == 200
    assert response.json()["data"]["config_status"] == "RUNNING"
    mock_get_status.assert_called_once_with(
        server_name="test-server", app_context=app_context
    )


@patch("bedrock_server_manager.web.routers.api_info.info_api.get_server_config_status")
def test_get_server_config_status_api_route_failure(
    mock_get_status, authenticated_client
):
    """Test the get_server_config_status_api_route with a failed status."""
    app_context = MagicMock()
    authenticated_client.app.state.app_context = app_context
    mock_get_status.return_value = {
        "status": "error",
        "message": "Failed to get config status",
    }
    response = authenticated_client.get("/api/server/test-server/config_status")
    assert response.status_code == 500
    assert "Unexpected error getting config status." in response.json()["detail"]


@patch(
    "bedrock_server_manager.web.routers.api_info.info_api.get_server_installed_version"
)
def test_get_server_version_api_route_success(mock_get_version, authenticated_client):
    """Test the get_server_version_api_route with a successful version."""
    app_context = MagicMock()
    authenticated_client.app.state.app_context = app_context
    mock_get_version.return_value = {"status": "success", "installed_version": "1.2.3"}
    response = authenticated_client.get("/api/server/test-server/version")
    assert response.status_code == 200
    assert response.json()["data"]["version"] == "1.2.3"
    mock_get_version.assert_called_once_with(
        server_name="test-server", app_context=app_context
    )


@patch(
    "bedrock_server_manager.web.routers.api_info.info_api.get_server_installed_version"
)
def test_get_server_version_api_route_failure(mock_get_version, authenticated_client):
    """Test the get_server_version_api_route with a failed version."""
    app_context = MagicMock()
    authenticated_client.app.state.app_context = app_context
    mock_get_version.return_value = {
        "status": "error",
        "message": "Failed to get version",
    }
    response = authenticated_client.get("/api/server/test-server/version")
    assert response.status_code == 500
    assert "Unexpected error getting installed version." in response.json()["detail"]


@patch("bedrock_server_manager.web.routers.api_info.utils_api.validate_server_exist")
def test_validate_server_api_route_success(mock_validate, authenticated_client):
    """Test the validate_server_api_route with a successful validation."""
    app_context = MagicMock()
    authenticated_client.app.state.app_context = app_context
    mock_validate.return_value = {"status": "success"}
    response = authenticated_client.get("/api/server/test-server/validate")
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    mock_validate.assert_called_once_with(
        server_name="test-server", app_context=app_context
    )


@patch("bedrock_server_manager.web.routers.api_info.utils_api.validate_server_exist")
def test_validate_server_api_route_failure(mock_validate, authenticated_client):
    """Test the validate_server_api_route with a failed validation."""
    app_context = MagicMock()
    authenticated_client.app.state.app_context = app_context
    mock_validate.return_value = {"status": "error", "message": "Validation failed"}
    response = authenticated_client.get("/api/server/test-server/validate")
    assert response.status_code == 500
    assert "Unexpected error validating server." in response.json()["detail"]


@patch(
    "bedrock_server_manager.web.routers.api_info.system_api.get_bedrock_process_info"
)
def test_server_process_info_api_route_success(mock_get_info, authenticated_client):
    """Test the server_process_info_api_route with a successful info retrieval."""
    app_context = MagicMock()
    authenticated_client.app.state.app_context = app_context
    mock_get_info.return_value = {"status": "success", "process_info": {"pid": 123}}
    response = authenticated_client.get("/api/server/test-server/process_info")
    assert response.status_code == 200
    assert response.json()["data"]["process_info"]["pid"] == 123
    mock_get_info.assert_called_once_with(
        server_name="test-server", app_context=app_context
    )


@patch(
    "bedrock_server_manager.web.routers.api_info.system_api.get_bedrock_process_info"
)
def test_server_process_info_api_route_failure(mock_get_info, authenticated_client):
    """Test the server_process_info_api_route with a failed info retrieval."""
    app_context = MagicMock()
    authenticated_client.app.state.app_context = app_context
    mock_get_info.return_value = {
        "status": "error",
        "message": "Failed to get process info",
    }
    response = authenticated_client.get("/api/server/test-server/process_info")
    assert response.status_code == 500
    assert "Unexpected error getting process info." in response.json()["detail"]


@patch(
    "bedrock_server_manager.web.routers.api_info.player_api.scan_and_update_player_db_api"
)
def test_scan_players_api_route_success(mock_scan, authenticated_client):
    """Test the scan_players_api_route with a successful scan."""
    app_context = MagicMock()
    authenticated_client.app.state.app_context = app_context
    mock_scan.return_value = {"status": "success"}
    response = authenticated_client.post("/api/players/scan")
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    mock_scan.assert_called_once_with(app_context=app_context)


@patch(
    "bedrock_server_manager.web.routers.api_info.player_api.scan_and_update_player_db_api"
)
def test_scan_players_api_route_failure(mock_scan, authenticated_client):
    """Test the scan_players_api_route with a failed scan."""
    app_context = MagicMock()
    authenticated_client.app.state.app_context = app_context
    mock_scan.return_value = {"status": "error", "message": "Scan failed"}
    response = authenticated_client.post("/api/players/scan")
    assert response.status_code == 500
    assert "Unexpected error scanning player logs." in response.json()["detail"]


@patch(
    "bedrock_server_manager.web.routers.api_info.player_api.get_all_known_players_api"
)
def test_get_all_players_api_route_success(mock_get_players, authenticated_client):
    """Test the get_all_players_api_route with a successful retrieval."""
    app_context = MagicMock()
    authenticated_client.app.state.app_context = app_context
    mock_get_players.return_value = {"status": "success", "players": []}
    response = authenticated_client.get("/api/players/get")
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    mock_get_players.assert_called_once_with(app_context=app_context)


@patch(
    "bedrock_server_manager.web.routers.api_info.player_api.get_all_known_players_api"
)
def test_get_all_players_api_route_failure(mock_get_players, authenticated_client):
    """Test the get_all_players_api_route with a failed retrieval."""
    app_context = MagicMock()
    authenticated_client.app.state.app_context = app_context
    mock_get_players.return_value = {
        "status": "error",
        "message": "Failed to get players",
    }
    response = authenticated_client.get("/api/players/get")
    assert response.status_code == 500
    assert (
        "A critical unexpected server error occurred while fetching players."
        in response.json()["detail"]
    )


@patch("bedrock_server_manager.web.routers.api_info.misc_api.prune_download_cache")
def test_prune_downloads_api_route_success(mock_prune, authenticated_client):
    """Test the prune_downloads_api_route with a successful prune."""
    app_context = MagicMock()
    authenticated_client.app.state.app_context = app_context
    mock_prune.return_value = {"status": "success"}
    with patch("os.path.isdir", return_value=True):
        response = authenticated_client.post(
            "/api/downloads/prune", json={"directory": "stable"}
        )
    assert response.status_code == 200
    assert response.json()["status"] == "success"


@patch("bedrock_server_manager.web.routers.api_info.misc_api.prune_download_cache")
def test_prune_downloads_api_route_failure(mock_prune, authenticated_client):
    """Test the prune_downloads_api_route with a failed prune."""
    app_context = MagicMock()
    authenticated_client.app.state.app_context = app_context
    mock_prune.return_value = {"status": "error", "message": "Prune failed"}
    with patch("os.path.isdir", return_value=True):
        response = authenticated_client.post(
            "/api/downloads/prune", json={"directory": "stable"}
        )
    assert response.status_code == 500
    assert (
        "An unexpected error occurred during the pruning process."
        in response.json()["detail"]
    )


@patch("bedrock_server_manager.web.routers.api_info.app_api.get_all_servers_data")
def test_get_servers_list_api_route_success(mock_get_servers, authenticated_client):
    """Test the get_servers_list_api_route with a successful retrieval."""
    app_context = MagicMock()
    authenticated_client.app.state.app_context = app_context
    mock_get_servers.return_value = {"status": "success", "servers": []}
    response = authenticated_client.get("/api/servers")
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    mock_get_servers.assert_called_once_with(app_context=app_context)


@patch("bedrock_server_manager.web.routers.api_info.app_api.get_all_servers_data")
def test_get_servers_list_api_route_failure(mock_get_servers, authenticated_client):
    """Test the get_servers_list_api_route with a failed retrieval."""
    app_context = MagicMock()
    authenticated_client.app.state.app_context = app_context
    mock_get_servers.return_value = {
        "status": "error",
        "message": "Failed to get servers",
    }
    response = authenticated_client.get("/api/servers")
    assert response.status_code == 500
    assert (
        "An unexpected error occurred retrieving the server list."
        in response.json()["detail"]
    )


@patch("bedrock_server_manager.web.routers.api_info.utils_api.get_system_and_app_info")
def test_get_system_info_api_route_success(mock_get_info, authenticated_client):
    """Test the get_system_info_api_route with a successful retrieval."""
    app_context = MagicMock()
    authenticated_client.app.state.app_context = app_context
    mock_get_info.return_value = {"status": "success", "data": {}}
    response = authenticated_client.get("/api/info")
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    mock_get_info.assert_called_once_with(app_context=app_context)


@patch("bedrock_server_manager.web.routers.api_info.utils_api.get_system_and_app_info")
def test_get_system_info_api_route_failure(mock_get_info, authenticated_client):
    """Test the get_system_info_api_route with a failed retrieval."""
    app_context = MagicMock()
    authenticated_client.app.state.app_context = app_context
    mock_get_info.return_value = {
        "status": "error",
        "message": "Failed to get system info",
    }
    response = authenticated_client.get("/api/info")
    assert response.status_code == 500
    assert (
        "An unexpected error occurred retrieving system info."
        in response.json()["detail"]
    )


@patch(
    "bedrock_server_manager.web.routers.api_info.player_api.add_players_manually_api"
)
def test_add_players_api_route_success(mock_add_players, authenticated_client):
    """Test the add_players_api_route with a successful add."""
    app_context = MagicMock()
    authenticated_client.app.state.app_context = app_context
    mock_add_players.return_value = {"status": "success"}
    response = authenticated_client.post(
        "/api/players/add", json={"players": ["player1:123"]}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    mock_add_players.assert_called_once_with(
        player_strings=["player1:123"], app_context=app_context
    )


@patch(
    "bedrock_server_manager.web.routers.api_info.player_api.add_players_manually_api"
)
def test_add_players_api_route_failure(mock_add_players, authenticated_client):
    """Test the add_players_api_route with a failed add."""
    app_context = MagicMock()
    authenticated_client.app.state.app_context = app_context
    mock_add_players.return_value = {
        "status": "error",
        "message": "Failed to add players",
    }
    response = authenticated_client.post(
        "/api/players/add", json={"players": ["player1:123"]}
    )
    assert response.status_code == 500
    assert (
        "A critical unexpected server error occurred while adding players."
        in response.json()["detail"]
    )
