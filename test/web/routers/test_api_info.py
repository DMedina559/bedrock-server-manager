import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from bedrock_server_manager.web.main import app
from bedrock_server_manager.web.dependencies import validate_server_exists
from bedrock_server_manager.web.auth_utils import create_access_token
from datetime import timedelta
import os

# Test data
TEST_USER = "testuser"


@pytest.fixture
def client():
    """Create a test client for the app, with authentication and mocked dependencies."""
    os.environ["BEDROCK_SERVER_MANAGER_USERNAME"] = TEST_USER
    os.environ["BEDROCK_SERVER_MANAGER_PASSWORD"] = "testpassword"
    os.environ["BEDROCK_SERVER_MANAGER_SECRET_KEY"] = "test-secret-key"

    app.dependency_overrides[validate_server_exists] = lambda: "test-server"

    access_token = create_access_token(
        data={"sub": TEST_USER}, expires_delta=timedelta(minutes=15)
    )
    client = TestClient(app)
    client.headers["Authorization"] = f"Bearer {access_token}"

    yield client

    del os.environ["BEDROCK_SERVER_MANAGER_USERNAME"]
    del os.environ["BEDROCK_SERVER_MANAGER_PASSWORD"]
    del os.environ["BEDROCK_SERVER_MANAGER_SECRET_KEY"]
    app.dependency_overrides = {}


@patch("bedrock_server_manager.web.routers.api_info.info_api.get_server_running_status")
def test_get_server_running_status_api_route_success(mock_get_status, client):
    """Test the get_server_running_status_api_route with a successful status."""
    mock_get_status.return_value = {"status": "success", "running": True}
    response = client.get("/api/server/test-server/status")
    assert response.status_code == 200
    assert response.json()["data"]["running"] is True


@patch("bedrock_server_manager.web.routers.api_info.info_api.get_server_running_status")
def test_get_server_running_status_api_route_failure(mock_get_status, client):
    """Test the get_server_running_status_api_route with a failed status."""
    mock_get_status.return_value = {
        "status": "error",
        "message": "Failed to get status",
    }
    response = client.get("/api/server/test-server/status")
    assert response.status_code == 500
    assert "Unexpected error checking running status." in response.json()["detail"]


@patch("bedrock_server_manager.web.routers.api_info.info_api.get_server_config_status")
def test_get_server_config_status_api_route_success(mock_get_status, client):
    """Test the get_server_config_status_api_route with a successful status."""
    mock_get_status.return_value = {"status": "success", "config_status": "RUNNING"}
    response = client.get("/api/server/test-server/config_status")
    assert response.status_code == 200
    assert response.json()["data"]["config_status"] == "RUNNING"


@patch("bedrock_server_manager.web.routers.api_info.info_api.get_server_config_status")
def test_get_server_config_status_api_route_failure(mock_get_status, client):
    """Test the get_server_config_status_api_route with a failed status."""
    mock_get_status.return_value = {
        "status": "error",
        "message": "Failed to get config status",
    }
    response = client.get("/api/server/test-server/config_status")
    assert response.status_code == 500
    assert "Unexpected error getting config status." in response.json()["detail"]


@patch(
    "bedrock_server_manager.web.routers.api_info.info_api.get_server_installed_version"
)
def test_get_server_version_api_route_success(mock_get_version, client):
    """Test the get_server_version_api_route with a successful version."""
    mock_get_version.return_value = {"status": "success", "installed_version": "1.2.3"}
    response = client.get("/api/server/test-server/version")
    assert response.status_code == 200
    assert response.json()["data"]["version"] == "1.2.3"


@patch(
    "bedrock_server_manager.web.routers.api_info.info_api.get_server_installed_version"
)
def test_get_server_version_api_route_failure(mock_get_version, client):
    """Test the get_server_version_api_route with a failed version."""
    mock_get_version.return_value = {
        "status": "error",
        "message": "Failed to get version",
    }
    response = client.get("/api/server/test-server/version")
    assert response.status_code == 500
    assert "Unexpected error getting installed version." in response.json()["detail"]


@patch("bedrock_server_manager.web.routers.api_info.utils_api.validate_server_exist")
def test_validate_server_api_route_success(mock_validate, client):
    """Test the validate_server_api_route with a successful validation."""
    mock_validate.return_value = {"status": "success"}
    response = client.get("/api/server/test-server/validate")
    assert response.status_code == 200
    assert response.json()["status"] == "success"


@patch("bedrock_server_manager.web.routers.api_info.utils_api.validate_server_exist")
def test_validate_server_api_route_failure(mock_validate, client):
    """Test the validate_server_api_route with a failed validation."""
    mock_validate.return_value = {"status": "error", "message": "Validation failed"}
    response = client.get("/api/server/test-server/validate")
    assert response.status_code == 500
    assert "Unexpected error validating server." in response.json()["detail"]


@patch(
    "bedrock_server_manager.web.routers.api_info.system_api.get_bedrock_process_info"
)
def test_server_process_info_api_route_success(mock_get_info, client):
    """Test the server_process_info_api_route with a successful info retrieval."""
    mock_get_info.return_value = {"status": "success", "process_info": {"pid": 123}}
    response = client.get("/api/server/test-server/process_info")
    assert response.status_code == 200
    assert response.json()["data"]["process_info"]["pid"] == 123


@patch(
    "bedrock_server_manager.web.routers.api_info.system_api.get_bedrock_process_info"
)
def test_server_process_info_api_route_failure(mock_get_info, client):
    """Test the server_process_info_api_route with a failed info retrieval."""
    mock_get_info.return_value = {
        "status": "error",
        "message": "Failed to get process info",
    }
    response = client.get("/api/server/test-server/process_info")
    assert response.status_code == 500
    assert "Unexpected error getting process info." in response.json()["detail"]


@patch(
    "bedrock_server_manager.web.routers.api_info.player_api.scan_and_update_player_db_api"
)
def test_scan_players_api_route_success(mock_scan, client):
    """Test the scan_players_api_route with a successful scan."""
    mock_scan.return_value = {"status": "success"}
    response = client.post("/api/players/scan")
    assert response.status_code == 200
    assert response.json()["status"] == "success"


@patch(
    "bedrock_server_manager.web.routers.api_info.player_api.scan_and_update_player_db_api"
)
def test_scan_players_api_route_failure(mock_scan, client):
    """Test the scan_players_api_route with a failed scan."""
    mock_scan.return_value = {"status": "error", "message": "Scan failed"}
    response = client.post("/api/players/scan")
    assert response.status_code == 500
    assert "Unexpected error scanning player logs." in response.json()["detail"]


@patch(
    "bedrock_server_manager.web.routers.api_info.player_api.get_all_known_players_api"
)
def test_get_all_players_api_route_success(mock_get_players, client):
    """Test the get_all_players_api_route with a successful retrieval."""
    mock_get_players.return_value = {"status": "success", "players": []}
    response = client.get("/api/players/get")
    assert response.status_code == 200
    assert response.json()["status"] == "success"


@patch(
    "bedrock_server_manager.web.routers.api_info.player_api.get_all_known_players_api"
)
def test_get_all_players_api_route_failure(mock_get_players, client):
    """Test the get_all_players_api_route with a failed retrieval."""
    mock_get_players.return_value = {
        "status": "error",
        "message": "Failed to get players",
    }
    response = client.get("/api/players/get")
    assert response.status_code == 500
    assert (
        "A critical unexpected server error occurred while fetching players."
        in response.json()["detail"]
    )


@patch("bedrock_server_manager.web.routers.api_info.misc_api.prune_download_cache")
def test_prune_downloads_api_route_success(mock_prune, client):
    """Test the prune_downloads_api_route with a successful prune."""
    mock_prune.return_value = {"status": "success"}
    with patch("os.path.isdir", return_value=True):
        response = client.post("/api/downloads/prune", json={"directory": "stable"})
    assert response.status_code == 200
    assert response.json()["status"] == "success"


@patch("bedrock_server_manager.web.routers.api_info.misc_api.prune_download_cache")
def test_prune_downloads_api_route_failure(mock_prune, client):
    """Test the prune_downloads_api_route with a failed prune."""
    mock_prune.return_value = {"status": "error", "message": "Prune failed"}
    with patch("os.path.isdir", return_value=True):
        response = client.post("/api/downloads/prune", json={"directory": "stable"})
    assert response.status_code == 500
    assert (
        "An unexpected error occurred during the pruning process."
        in response.json()["detail"]
    )


@patch("bedrock_server_manager.web.routers.api_info.app_api.get_all_servers_data")
def test_get_servers_list_api_route_success(mock_get_servers, client):
    """Test the get_servers_list_api_route with a successful retrieval."""
    mock_get_servers.return_value = {"status": "success", "servers": []}
    response = client.get("/api/servers")
    assert response.status_code == 200
    assert response.json()["status"] == "success"


@patch("bedrock_server_manager.web.routers.api_info.app_api.get_all_servers_data")
def test_get_servers_list_api_route_failure(mock_get_servers, client):
    """Test the get_servers_list_api_route with a failed retrieval."""
    mock_get_servers.return_value = {
        "status": "error",
        "message": "Failed to get servers",
    }
    response = client.get("/api/servers")
    assert response.status_code == 500
    assert (
        "An unexpected error occurred retrieving the server list."
        in response.json()["detail"]
    )


@patch("bedrock_server_manager.web.routers.api_info.utils_api.get_system_and_app_info")
def test_get_system_info_api_route_success(mock_get_info, client):
    """Test the get_system_info_api_route with a successful retrieval."""
    mock_get_info.return_value = {"status": "success", "data": {}}
    response = client.get("/api/info")
    assert response.status_code == 200
    assert response.json()["status"] == "success"


@patch("bedrock_server_manager.web.routers.api_info.utils_api.get_system_and_app_info")
def test_get_system_info_api_route_failure(mock_get_info, client):
    """Test the get_system_info_api_route with a failed retrieval."""
    mock_get_info.return_value = {
        "status": "error",
        "message": "Failed to get system info",
    }
    response = client.get("/api/info")
    assert response.status_code == 500
    assert (
        "An unexpected error occurred retrieving system info."
        in response.json()["detail"]
    )


@patch(
    "bedrock_server_manager.web.routers.api_info.player_api.add_players_manually_api"
)
def test_add_players_api_route_success(mock_add_players, client):
    """Test the add_players_api_route with a successful add."""
    mock_add_players.return_value = {"status": "success"}
    response = client.post("/api/players/add", json={"players": ["player1:123"]})
    assert response.status_code == 200
    assert response.json()["status"] == "success"


@patch(
    "bedrock_server_manager.web.routers.api_info.player_api.add_players_manually_api"
)
def test_add_players_api_route_failure(mock_add_players, client):
    """Test the add_players_api_route with a failed add."""
    mock_add_players.return_value = {
        "status": "error",
        "message": "Failed to add players",
    }
    response = client.post("/api/players/add", json={"players": ["player1:123"]})
    assert response.status_code == 500
    assert (
        "A critical unexpected server error occurred while adding players."
        in response.json()["detail"]
    )
