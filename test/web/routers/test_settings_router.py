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


def test_manage_settings_page_route(client):
    """Test the manage_settings_page_route with a successful response."""
    response = client.get("/settings")
    assert response.status_code == 200
    assert "Global Settings" in response.text


@patch(
    "bedrock_server_manager.web.routers.settings.settings_api.get_all_global_settings"
)
def test_get_all_settings_api_route(mock_get_all_settings, client):
    """Test the get_all_settings_api_route with a successful response."""
    mock_get_all_settings.return_value = {"status": "success", "data": {}}
    response = client.get("/api/settings")
    assert response.status_code == 200
    assert response.json()["status"] == "success"


@patch("bedrock_server_manager.web.routers.settings.settings_api.set_global_setting")
def test_set_setting_api_route(mock_set_setting, client):
    """Test the set_setting_api_route with a successful response."""
    mock_set_setting.return_value = {"status": "success"}
    response = client.post(
        "/api/settings", json={"key": "test_key", "value": "test_value"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"


@patch("bedrock_server_manager.web.routers.settings.get_settings_instance")
@patch("bedrock_server_manager.web.routers.settings.os.path.isdir")
@patch("bedrock_server_manager.web.routers.settings.os.listdir")
def test_get_themes_api_route(mock_listdir, mock_isdir, mock_get_settings, client):
    """Test the get_themes_api_route with a successful response."""
    mock_get_settings.return_value.get.return_value = "/fake/path"
    mock_isdir.return_value = True
    mock_listdir.return_value = ["theme1.css", "theme2.css"]

    response = client.get("/api/themes")
    assert response.status_code == 200
    assert "theme1" in response.json()
    assert "theme2" in response.json()


@patch(
    "bedrock_server_manager.web.routers.settings.settings_api.reload_global_settings"
)
def test_reload_settings_api_route(mock_reload_settings, client):
    """Test the reload_settings_api_route with a successful response."""
    mock_reload_settings.return_value = {"status": "success"}
    response = client.post("/api/settings/reload")
    assert response.status_code == 200
    assert response.json()["status"] == "success"


@patch("bedrock_server_manager.web.routers.settings.settings_api.set_global_setting")
def test_set_setting_api_route_user_input_error(mock_set_setting, client):
    """Test the set_setting_api_route with a UserInputError."""
    from bedrock_server_manager.error import UserInputError

    mock_set_setting.side_effect = UserInputError("Invalid key")
    response = client.post(
        "/api/settings", json={"key": "invalid_key", "value": "test_value"}
    )
    assert response.status_code == 400
    assert "Invalid key" in response.json()["detail"]


@patch("bedrock_server_manager.web.routers.settings.settings_api.set_global_setting")
def test_set_setting_api_route_bsm_error(mock_set_setting, client):
    """Test the set_setting_api_route with a BSMError."""
    from bedrock_server_manager.error import BSMError

    mock_set_setting.side_effect = BSMError("Failed to set setting")
    response = client.post(
        "/api/settings", json={"key": "test_key", "value": "test_value"}
    )
    assert response.status_code == 500
    assert "Failed to set setting" in response.json()["detail"]


@patch(
    "bedrock_server_manager.web.routers.settings.settings_api.reload_global_settings"
)
def test_reload_settings_api_route_bsm_error(mock_reload_settings, client):
    """Test the reload_settings_api_route with a BSMError."""
    from bedrock_server_manager.error import BSMError

    mock_reload_settings.side_effect = BSMError("Failed to reload settings")
    response = client.post("/api/settings/reload")
    assert response.status_code == 500
    assert "Failed to reload settings" in response.json()["detail"]
