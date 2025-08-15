from unittest.mock import patch, MagicMock
import pytest


def test_get_server_running_status_api_route_success(
    authenticated_client, real_bedrock_server
):
    """Test the get_server_running_status_api_route with a successful status."""
    response = authenticated_client.get("/api/server/test_server/status")
    assert response.status_code == 200
    assert response.json()["data"]["running"] is False


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


def test_get_server_config_status_api_route_success(
    authenticated_client, real_bedrock_server
):
    """Test the get_server_config_status_api_route with a successful status."""
    real_bedrock_server.set_status_in_config("STOPPED")
    response = authenticated_client.get("/api/server/test_server/config_status")
    assert response.status_code == 200
    assert response.json()["data"]["config_status"] == "STOPPED"


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


def test_get_server_version_api_route_success(
    authenticated_client, real_bedrock_server
):
    """Test the get_server_version_api_route with a successful version."""
    real_bedrock_server.set_version("1.2.3")
    response = authenticated_client.get("/api/server/test_server/version")
    assert response.status_code == 200
    assert response.json()["data"]["version"] == "1.2.3"


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


def test_validate_server_api_route_success(authenticated_client, real_bedrock_server):
    """Test the validate_server_api_route with a successful validation."""
    response = authenticated_client.get("/api/server/test_server/validate")
    assert response.status_code == 200
    assert response.json()["status"] == "success"


@patch("bedrock_server_manager.web.routers.api_info.utils_api.validate_server_exist")
def test_validate_server_api_route_failure(mock_validate, authenticated_client):
    """Test the validate_server_api_route with a failed validation."""
    app_context = MagicMock()
    authenticated_client.app.state.app_context = app_context
    mock_validate.return_value = {"status": "error", "message": "Validation failed"}
    response = authenticated_client.get("/api/server/test_server/validate")
    assert response.status_code == 404
    assert "Validation failed" in response.json()["detail"]


def test_server_process_info_api_route_success(
    authenticated_client, real_bedrock_server
):
    """Test the server_process_info_api_route with a successful info retrieval."""
    response = authenticated_client.get("/api/server/test_server/process_info")
    assert response.status_code == 200
    assert response.json()["data"]["process_info"] is None


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


def test_scan_players_api_route_success(authenticated_client, app_context):
    """Test the scan_players_api_route with a successful scan."""
    response = authenticated_client.post("/api/players/scan")
    assert response.status_code == 200
    assert response.json()["status"] == "success"


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


def test_get_all_players_api_route_success(authenticated_client, app_context):
    """Test the get_all_players_api_route with a successful retrieval."""
    response = authenticated_client.get("/api/players/get")
    assert response.status_code == 200
    assert response.json()["status"] == "success"


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


import os


def test_prune_downloads_api_route_success(authenticated_client, app_context):
    """Test the prune_downloads_api_route with a successful prune."""
    download_dir = os.path.join(app_context.settings.get("paths.downloads"), "stable")
    os.makedirs(download_dir)
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


def test_get_servers_list_api_route_success(
    authenticated_client, app_context, real_bedrock_server
):
    """Test the get_servers_list_api_route with a successful retrieval."""
    response = authenticated_client.get("/api/servers")
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert len(response.json()["servers"]) == 1


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


def test_get_system_info_api_route_success(authenticated_client, app_context):
    """Test the get_system_info_api_route with a successful retrieval."""
    response = authenticated_client.get("/api/info")
    assert response.status_code == 200
    assert response.json()["status"] == "success"


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


def test_add_players_api_route_success(authenticated_client, app_context):
    """Test the add_players_api_route with a successful add."""
    response = authenticated_client.post(
        "/api/players/add", json={"players": ["player1:123"]}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"


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
