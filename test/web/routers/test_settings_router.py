from unittest.mock import patch


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
