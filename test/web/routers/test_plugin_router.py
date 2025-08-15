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


def test_manage_plugins_page_route(client):
    """Test the manage_plugins_page_route with an authenticated user."""
    response = client.get("/plugins")
    assert response.status_code == 200
    assert "Bedrock Server Manager" in response.text


@patch("bedrock_server_manager.web.routers.plugin.plugins_api.get_plugin_statuses")
def test_get_plugins_status_api_route_success(mock_get_plugins, client):
    """Test the get_plugins_status_api_route with a successful response."""
    mock_get_plugins.return_value = {
        "status": "success",
        "plugins": {"plugin1": {"enabled": True}},
    }
    response = client.get("/api/plugins")
    assert response.status_code == 200
    assert response.json()["data"]["plugin1"]["enabled"] is True


@patch("bedrock_server_manager.web.routers.plugin.plugins_api.get_plugin_statuses")
def test_get_plugins_status_api_route_failure(mock_get_plugins, client):
    """Test the get_plugins_status_api_route with a failed response."""
    mock_get_plugins.return_value = {
        "status": "error",
        "message": "Failed to get plugins",
    }
    response = client.get("/api/plugins")
    assert response.status_code == 500
    assert (
        "An unexpected error occurred while getting plugin statuses."
        in response.json()["detail"]
    )


@patch(
    "bedrock_server_manager.web.routers.plugin.plugins_api.trigger_external_plugin_event_api"
)
def test_trigger_event_api_route_success(mock_trigger_event, client):
    """Test the trigger_event_api_route with a successful response."""
    mock_trigger_event.return_value = {"status": "success"}
    response = client.post(
        "/api/plugins/trigger_event",
        json={"event_name": "test_event", "payload": {}},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"


@patch(
    "bedrock_server_manager.web.routers.plugin.plugins_api.trigger_external_plugin_event_api"
)
def test_trigger_event_api_route_user_input_error(mock_trigger_event, client):
    """Test the trigger_event_api_route with a UserInputError."""
    from bedrock_server_manager.error import UserInputError

    mock_trigger_event.side_effect = UserInputError("Invalid event name")
    response = client.post(
        "/api/plugins/trigger_event",
        json={"event_name": "test_event", "payload": {}},
    )
    assert response.status_code == 400
    assert "Invalid event name" in response.json()["detail"]


@patch("bedrock_server_manager.web.routers.plugin.plugins_api.set_plugin_status")
def test_set_plugin_status_api_route_enable_success(mock_set_status, client):
    """Test enabling a plugin with a successful response."""
    mock_set_status.return_value = {"status": "success"}
    response = client.post("/api/plugins/plugin1", json={"enabled": True})
    assert response.status_code == 200
    assert response.json()["status"] == "success"


@patch("bedrock_server_manager.web.routers.plugin.plugins_api.set_plugin_status")
def test_set_plugin_status_api_route_disable_success(mock_set_status, client):
    """Test disabling a plugin with a successful response."""
    mock_set_status.return_value = {"status": "success"}
    response = client.post("/api/plugins/plugin1", json={"enabled": False})
    assert response.status_code == 200
    assert response.json()["status"] == "success"


@patch("bedrock_server_manager.web.routers.plugin.plugins_api.set_plugin_status")
def test_set_plugin_status_api_route_not_found(mock_set_status, client):
    """Test setting the status of a plugin that does not exist."""
    mock_set_status.return_value = {
        "status": "error",
        "message": "Plugin not found",
    }
    response = client.post("/api/plugins/plugin1", json={"enabled": True})
    assert response.status_code == 404
    assert "Plugin not found" in response.json()["detail"]


@patch("bedrock_server_manager.web.routers.plugin.plugins_api.reload_plugins")
def test_reload_plugins_api_route_success(mock_reload_plugins, client):
    """Test the reload_plugins_api_route with a successful response."""
    mock_reload_plugins.return_value = {"status": "success"}
    response = client.put("/api/plugins/reload")
    assert response.status_code == 200
    assert response.json()["status"] == "success"


@patch("bedrock_server_manager.web.routers.plugin.plugins_api.reload_plugins")
def test_reload_plugins_api_route_failure(mock_reload_plugins, client):
    """Test the reload_plugins_api_route with a failed response."""
    mock_reload_plugins.return_value = {
        "status": "error",
        "message": "Failed to reload plugins",
    }
    response = client.put("/api/plugins/reload")
    assert response.status_code == 500
    assert (
        "An unexpected error occurred while reloading plugins."
        in response.json()["detail"]
    )


@patch(
    "bedrock_server_manager.web.routers.plugin.plugins_api.trigger_external_plugin_event_api"
)
def test_trigger_event_api_route_bsm_error(mock_trigger_event, client):
    """Test the trigger_event_api_route with a BSMError."""
    from bedrock_server_manager.error import BSMError

    mock_trigger_event.side_effect = BSMError("Failed to trigger event")
    response = client.post(
        "/api/plugins/trigger_event",
        json={"event_name": "test_event", "payload": {}},
    )
    assert response.status_code == 500
    assert "Failed to trigger event" in response.json()["detail"]


@patch("bedrock_server_manager.web.routers.plugin.plugins_api.set_plugin_status")
def test_set_plugin_status_api_route_user_input_error(mock_set_status, client):
    """Test setting the status of a plugin with a UserInputError."""
    from bedrock_server_manager.error import UserInputError

    mock_set_status.side_effect = UserInputError("Invalid plugin name")
    response = client.post("/api/plugins/plugin1", json={"enabled": True})
    assert response.status_code == 400
    assert "Invalid plugin name" in response.json()["detail"]


@patch("bedrock_server_manager.web.routers.plugin.plugins_api.set_plugin_status")
def test_set_plugin_status_api_route_bsm_error(mock_set_status, client):
    """Test setting the status of a plugin with a BSMError."""
    from bedrock_server_manager.error import BSMError

    mock_set_status.side_effect = BSMError("Failed to set plugin status")
    response = client.post("/api/plugins/plugin1", json={"enabled": True})
    assert response.status_code == 500
    assert "Failed to set plugin status" in response.json()["detail"]


@patch("bedrock_server_manager.web.routers.plugin.plugins_api.reload_plugins")
def test_reload_plugins_api_route_bsm_error(mock_reload_plugins, client):
    """Test the reload_plugins_api_route with a BSMError."""
    from bedrock_server_manager.error import BSMError

    mock_reload_plugins.side_effect = BSMError("Failed to reload plugins")
    response = client.put("/api/plugins/reload")
    assert response.status_code == 500
    assert "Failed to reload plugins" in response.json()["detail"]
