from unittest.mock import patch, MagicMock
import pytest


def test_manage_settings_page_route(authenticated_client):
    """Test the manage_settings_page_route with a successful response."""
    response = authenticated_client.get("/settings")
    assert response.status_code == 200
    assert "Global Settings" in response.text


def test_get_all_settings_api_route(authenticated_client, app_context):
    """Test the get_all_settings_api_route with a successful response."""
    response = authenticated_client.get("/api/settings")
    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_set_setting_api_route(authenticated_client, app_context):
    """Test the set_setting_api_route with a successful response."""
    response = authenticated_client.post(
        "/api/settings", json={"key": "test_key", "value": "test_value"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"


import os


def test_get_themes_api_route(authenticated_client, app_context):
    """Test the get_themes_api_route with a successful response."""
    themes_dir = app_context.settings.get("paths.themes")
    os.makedirs(themes_dir, exist_ok=True)
    theme_file = os.path.join(themes_dir, "theme1.css")
    with open(theme_file, "w") as f:
        f.write("test")

    response = authenticated_client.get("/api/themes")
    assert response.status_code == 200
    assert "theme1" in response.json()


def test_reload_settings_api_route(authenticated_client, app_context):
    """Test the reload_settings_api_route with a successful response."""
    response = authenticated_client.post("/api/settings/reload")
    assert response.status_code == 200
    assert response.json()["status"] == "success"


@patch("bedrock_server_manager.web.routers.settings.settings_api.set_global_setting")
def test_set_setting_api_route_user_input_error(mock_set_setting, authenticated_client):
    """Test the set_setting_api_route with a UserInputError."""
    from bedrock_server_manager.error import UserInputError

    app_context = MagicMock()
    authenticated_client.app.state.app_context = app_context
    mock_set_setting.side_effect = UserInputError("Invalid key")
    response = authenticated_client.post(
        "/api/settings", json={"key": "invalid_key", "value": "test_value"}
    )
    assert response.status_code == 400
    assert "Invalid key" in response.json()["detail"]


@patch("bedrock_server_manager.web.routers.settings.settings_api.set_global_setting")
def test_set_setting_api_route_bsm_error(mock_set_setting, authenticated_client):
    """Test the set_setting_api_route with a BSMError."""
    from bedrock_server_manager.error import BSMError

    app_context = MagicMock()
    authenticated_client.app.state.app_context = app_context
    mock_set_setting.side_effect = BSMError("Failed to set setting")
    response = authenticated_client.post(
        "/api/settings", json={"key": "test_key", "value": "test_value"}
    )
    assert response.status_code == 500
    assert "Failed to set setting" in response.json()["detail"]


@patch(
    "bedrock_server_manager.web.routers.settings.settings_api.reload_global_settings"
)
def test_reload_settings_api_route_bsm_error(
    mock_reload_settings, authenticated_client
):
    """Test the reload_settings_api_route with a BSMError."""
    from bedrock_server_manager.error import BSMError

    app_context = MagicMock()
    authenticated_client.app.state.app_context = app_context
    mock_reload_settings.side_effect = BSMError("Failed to reload settings")
    response = authenticated_client.post("/api/settings/reload")
    assert response.status_code == 500
    assert "Failed to reload settings" in response.json()["detail"]
