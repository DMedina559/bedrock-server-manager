from unittest.mock import patch


def test_manage_plugins_page_route(authenticated_client):
    """Test the manage_plugins_page_route with an authenticated user."""
    response = authenticated_client.get("/plugins")
    assert response.status_code == 200
    assert "Bedrock Server Manager" in response.text


@patch("bedrock_server_manager.web.routers.plugin.plugins_api.get_plugin_statuses")
def test_get_plugins_status_api_route_success(mock_get_plugins, authenticated_client):
    """Test the get_plugins_status_api_route with a successful response."""
    mock_get_plugins.return_value = {
        "status": "success",
        "plugins": {"plugin1": {"enabled": True}},
    }
    response = authenticated_client.get("/api/plugins")
    assert response.status_code == 200
    assert response.json()["data"]["plugin1"]["enabled"] is True


@patch("bedrock_server_manager.web.routers.plugin.plugins_api.get_plugin_statuses")
def test_get_plugins_status_api_route_failure(mock_get_plugins, authenticated_client):
    """Test the get_plugins_status_api_route with a failed response."""
    mock_get_plugins.return_value = {
        "status": "error",
        "message": "Failed to get plugins",
    }
    response = authenticated_client.get("/api/plugins")
    assert response.status_code == 500
    assert (
        "An unexpected error occurred while getting plugin statuses."
        in response.json()["detail"]
    )


@patch(
    "bedrock_server_manager.web.routers.plugin.plugins_api.trigger_external_plugin_event_api"
)
def test_trigger_event_api_route_success(mock_trigger_event, authenticated_client):
    """Test the trigger_event_api_route with a successful response."""
    mock_trigger_event.return_value = {"status": "success"}
    response = authenticated_client.post(
        "/api/plugins/trigger_event",
        json={"event_name": "test_event", "payload": {}},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"


@patch(
    "bedrock_server_manager.web.routers.plugin.plugins_api.trigger_external_plugin_event_api"
)
def test_trigger_event_api_route_user_input_error(
    mock_trigger_event, authenticated_client
):
    """Test the trigger_event_api_route with a UserInputError."""
    from bedrock_server_manager.error import UserInputError

    mock_trigger_event.side_effect = UserInputError("Invalid event name")
    response = authenticated_client.post(
        "/api/plugins/trigger_event",
        json={"event_name": "test_event", "payload": {}},
    )
    assert response.status_code == 400
    assert "Invalid event name" in response.json()["detail"]


@patch("bedrock_server_manager.web.routers.plugin.plugins_api.set_plugin_status")
def test_set_plugin_status_api_route_enable_success(
    mock_set_status, authenticated_client
):
    """Test enabling a plugin with a successful response."""
    mock_set_status.return_value = {"status": "success"}
    response = authenticated_client.post("/api/plugins/plugin1", json={"enabled": True})
    assert response.status_code == 200
    assert response.json()["status"] == "success"


@patch("bedrock_server_manager.web.routers.plugin.plugins_api.set_plugin_status")
def test_set_plugin_status_api_route_disable_success(
    mock_set_status, authenticated_client
):
    """Test disabling a plugin with a successful response."""
    mock_set_status.return_value = {"status": "success"}
    response = authenticated_client.post(
        "/api/plugins/plugin1", json={"enabled": False}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"


@patch("bedrock_server_manager.web.routers.plugin.plugins_api.set_plugin_status")
def test_set_plugin_status_api_route_not_found(mock_set_status, authenticated_client):
    """Test setting the status of a plugin that does not exist."""
    from bedrock_server_manager.error import UserInputError

    mock_set_status.side_effect = UserInputError("Plugin not found")
    response = authenticated_client.post("/api/plugins/plugin1", json={"enabled": True})
    assert response.status_code == 400
    assert "Plugin not found" in response.json()["detail"]


@patch("bedrock_server_manager.web.routers.plugin.plugins_api.reload_plugins")
def test_reload_plugins_api_route_success(mock_reload_plugins, authenticated_client):
    """Test the reload_plugins_api_route with a successful response."""
    mock_reload_plugins.return_value = {"status": "success"}
    response = authenticated_client.put("/api/plugins/reload")
    assert response.status_code == 200
    assert response.json()["status"] == "success"


@patch("bedrock_server_manager.web.routers.plugin.plugins_api.reload_plugins")
def test_reload_plugins_api_route_failure(mock_reload_plugins, authenticated_client):
    """Test the reload_plugins_api_route with a failed response."""
    mock_reload_plugins.return_value = {
        "status": "error",
        "message": "Failed to reload plugins",
    }
    response = authenticated_client.put("/api/plugins/reload")
    assert response.status_code == 500
    assert (
        "An unexpected error occurred while reloading plugins."
        in response.json()["detail"]
    )


@patch(
    "bedrock_server_manager.web.routers.plugin.plugins_api.trigger_external_plugin_event_api"
)
def test_trigger_event_api_route_bsm_error(mock_trigger_event, authenticated_client):
    """Test the trigger_event_api_route with a BSMError."""
    from bedrock_server_manager.error import BSMError

    mock_trigger_event.side_effect = BSMError("Failed to trigger event")
    response = authenticated_client.post(
        "/api/plugins/trigger_event",
        json={"event_name": "test_event", "payload": {}},
    )
    assert response.status_code == 500
    assert "Failed to trigger event" in response.json()["detail"]


@patch("bedrock_server_manager.web.routers.plugin.plugins_api.set_plugin_status")
def test_set_plugin_status_api_route_user_input_error(
    mock_set_status, authenticated_client
):
    """Test setting the status of a plugin with a UserInputError."""
    from bedrock_server_manager.error import UserInputError

    mock_set_status.side_effect = UserInputError("Invalid plugin name")
    response = authenticated_client.post("/api/plugins/plugin1", json={"enabled": True})
    assert response.status_code == 400
    assert "Invalid plugin name" in response.json()["detail"]


@patch("bedrock_server_manager.web.routers.plugin.plugins_api.set_plugin_status")
def test_set_plugin_status_api_route_bsm_error(mock_set_status, authenticated_client):
    """Test setting the status of a plugin with a BSMError."""
    from bedrock_server_manager.error import BSMError

    mock_set_status.side_effect = BSMError("Failed to set plugin status")
    response = authenticated_client.post("/api/plugins/plugin1", json={"enabled": True})
    assert response.status_code == 500
    assert "Failed to set plugin status" in response.json()["detail"]


@patch("bedrock_server_manager.web.routers.plugin.plugins_api.reload_plugins")
def test_reload_plugins_api_route_bsm_error(mock_reload_plugins, authenticated_client):
    """Test the reload_plugins_api_route with a BSMError."""
    from bedrock_server_manager.error import BSMError

    mock_reload_plugins.side_effect = BSMError("Failed to reload plugins")
    response = authenticated_client.put("/api/plugins/reload")
    assert response.status_code == 500
    assert "Failed to reload plugins" in response.json()["detail"]
