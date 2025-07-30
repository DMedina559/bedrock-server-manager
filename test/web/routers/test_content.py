from unittest.mock import patch


@patch("bedrock_server_manager.web.routers.content.app_api.list_available_worlds_api")
def test_list_worlds_api_route_success(mock_list_worlds, client):
    """Test the list_worlds_api_route with a successful response."""
    mock_list_worlds.return_value = {
        "status": "success",
        "files": ["world1.mcworld", "world2.mcworld"],
    }
    response = client.get("/api/content/worlds")
    assert response.status_code == 200
    assert response.json()["files"] == ["world1.mcworld", "world2.mcworld"]


@patch("bedrock_server_manager.web.routers.content.app_api.list_available_worlds_api")
def test_list_worlds_api_route_failure(mock_list_worlds, client):
    """Test the list_worlds_api_route with a failed response."""
    mock_list_worlds.return_value = {
        "status": "error",
        "message": "Failed to list worlds",
    }
    response = client.get("/api/content/worlds")
    assert response.status_code == 500
    assert (
        "A critical server error occurred while listing worlds."
        in response.json()["detail"]
    )


@patch("bedrock_server_manager.web.routers.content.app_api.list_available_addons_api")
def test_list_addons_api_route_success(mock_list_addons, client):
    """Test the list_addons_api_route with a successful response."""
    mock_list_addons.return_value = {
        "status": "success",
        "files": ["addon1.mcaddon", "addon2.mcpack"],
    }
    response = client.get("/api/content/addons")
    assert response.status_code == 200
    assert response.json()["files"] == ["addon1.mcaddon", "addon2.mcpack"]


@patch("bedrock_server_manager.web.routers.content.app_api.list_available_addons_api")
def test_list_addons_api_route_failure(mock_list_addons, client):
    """Test the list_addons_api_route with a failed response."""
    mock_list_addons.return_value = {
        "status": "error",
        "message": "Failed to list addons",
    }
    response = client.get("/api/content/addons")
    assert response.status_code == 500
    assert (
        "A critical server error occurred while listing addons."
        in response.json()["detail"]
    )


@patch("bedrock_server_manager.web.routers.content.utils_api.validate_server_exist")
@patch("bedrock_server_manager.web.routers.content.os.path.isfile")
def test_install_world_api_route_success(
    mock_isfile, mock_validate_server, client, mock_get_settings_instance
):
    """Test the install_world_api_route with a successful response."""
    mock_validate_server.return_value = True
    mock_isfile.return_value = True
    mock_get_settings_instance.get.return_value = "/fake/path"

    response = client.post(
        "/api/server/test-server/world/install",
        json={"filename": "world.mcworld"},
    )
    assert response.status_code == 202
    assert "initiated in background" in response.json()["message"]


@patch("bedrock_server_manager.web.routers.content.utils_api.validate_server_exist")
@patch("bedrock_server_manager.web.routers.content.os.path.isfile")
def test_install_world_api_route_not_found(
    mock_isfile, mock_validate_server, client, mock_get_settings_instance
):
    """Test the install_world_api_route with a file not found error."""
    mock_validate_server.return_value = True
    mock_isfile.return_value = False
    mock_get_settings_instance.get.return_value = "/fake/path"

    response = client.post(
        "/api/server/test-server/world/install",
        json={"filename": "world.mcworld"},
    )
    assert response.status_code == 404
    assert "not found for import" in response.json()["detail"]


@patch("bedrock_server_manager.web.routers.content.world_api.import_world")
def test_install_world_api_route_user_input_error(mock_import_world, client, caplog):
    """Test the install_world_api_route with a UserInputError."""
    from bedrock_server_manager.error import UserInputError

    mock_import_world.side_effect = UserInputError("Invalid world file")
    with patch("os.path.isfile", return_value=True):
        response = client.post(
            "/api/server/test-server/world/install",
            json={"filename": "world.mcworld"},
        )
    assert response.status_code == 202
    assert "Invalid world file" in caplog.text


@patch("bedrock_server_manager.web.routers.content.world_api.import_world")
def test_install_world_api_route_bsm_error(mock_import_world, client, caplog):
    """Test the install_world_api_route with a BSMError."""
    from bedrock_server_manager.error import BSMError

    mock_import_world.side_effect = BSMError("Failed to import world")
    with patch("os.path.isfile", return_value=True):
        response = client.post(
            "/api/server/test-server/world/install",
            json={"filename": "world.mcworld"},
        )
    assert response.status_code == 202
    assert "Failed to import world" in caplog.text


@patch("bedrock_server_manager.web.routers.content.world_api.export_world")
def test_export_world_api_route_user_input_error(mock_export_world, client, caplog):
    """Test the export_world_api_route with a UserInputError."""
    from bedrock_server_manager.error import UserInputError

    mock_export_world.side_effect = UserInputError("Invalid server name")
    response = client.post("/api/server/test-server/world/export")
    assert response.status_code == 202
    assert "Invalid server name" in caplog.text


@patch("bedrock_server_manager.web.routers.content.world_api.export_world")
def test_export_world_api_route_bsm_error(mock_export_world, client, caplog):
    """Test the export_world_api_route with a BSMError."""
    from bedrock_server_manager.error import BSMError

    mock_export_world.side_effect = BSMError("Failed to export world")
    response = client.post("/api/server/test-server/world/export")
    assert response.status_code == 202
    assert "Failed to export world" in caplog.text


@patch("bedrock_server_manager.web.routers.content.world_api.reset_world")
def test_reset_world_api_route_user_input_error(mock_reset_world, client, caplog):
    """Test the reset_world_api_route with a UserInputError."""
    from bedrock_server_manager.error import UserInputError

    mock_reset_world.side_effect = UserInputError("Invalid server name")
    response = client.delete("/api/server/test-server/world/reset")
    assert response.status_code == 202
    assert "Invalid server name" in caplog.text


@patch("bedrock_server_manager.web.routers.content.world_api.reset_world")
def test_reset_world_api_route_bsm_error(mock_reset_world, client, caplog):
    """Test the reset_world_api_route with a BSMError."""
    from bedrock_server_manager.error import BSMError

    mock_reset_world.side_effect = BSMError("Failed to reset world")
    response = client.delete("/api/server/test-server/world/reset")
    assert response.status_code == 202
    assert "Failed to reset world" in caplog.text


@patch("bedrock_server_manager.web.routers.content.addon_api.import_addon")
def test_install_addon_api_route_user_input_error(mock_import_addon, client, caplog):
    """Test the install_addon_api_route with a UserInputError."""
    from bedrock_server_manager.error import UserInputError

    mock_import_addon.side_effect = UserInputError("Invalid addon file")
    with patch("os.path.isfile", return_value=True):
        response = client.post(
            "/api/server/test-server/addon/install",
            json={"filename": "addon.mcaddon"},
        )
    assert response.status_code == 202
    assert "Invalid addon file" in caplog.text


@patch("bedrock_server_manager.web.routers.content.addon_api.import_addon")
def test_install_addon_api_route_bsm_error(mock_import_addon, client, caplog):
    """Test the install_addon_api_route with a BSMError."""
    from bedrock_server_manager.error import BSMError

    mock_import_addon.side_effect = BSMError("Failed to import addon")
    with patch("os.path.isfile", return_value=True):
        response = client.post(
            "/api/server/test-server/addon/install",
            json={"filename": "addon.mcaddon"},
        )
    assert response.status_code == 202
    assert "Failed to import addon" in caplog.text


@patch("bedrock_server_manager.web.routers.content.utils_api.validate_server_exist")
def test_export_world_api_route_success(mock_validate_server, client):
    """Test the export_world_api_route with a successful response."""
    mock_validate_server.return_value = True

    response = client.post("/api/server/test-server/world/export")
    assert response.status_code == 202
    assert "initiated in background" in response.json()["message"]


@patch("bedrock_server_manager.web.routers.content.utils_api.validate_server_exist")
def test_reset_world_api_route_success(mock_validate_server, client):
    """Test the reset_world_api_route with a successful response."""
    mock_validate_server.return_value = True

    response = client.delete("/api/server/test-server/world/reset")
    assert response.status_code == 202
    assert "initiated in background" in response.json()["message"]


@patch("bedrock_server_manager.web.routers.content.utils_api.validate_server_exist")
@patch("bedrock_server_manager.web.routers.content.os.path.isfile")
@patch("bedrock_server_manager.web.routers.content.get_settings_instance")
def test_install_addon_api_route_success(
    mock_get_settings, mock_isfile, mock_validate_server, client
):
    """Test the install_addon_api_route with a successful response."""
    mock_validate_server.return_value = True
    mock_isfile.return_value = True
    mock_get_settings.return_value.get.return_value = "/fake/path"

    response = client.post(
        "/api/server/test-server/addon/install",
        json={"filename": "addon.mcaddon"},
    )
    assert response.status_code == 202
    assert "initiated in background" in response.json()["message"]


@patch("bedrock_server_manager.web.routers.content.utils_api.validate_server_exist")
@patch("bedrock_server_manager.web.routers.content.os.path.isfile")
@patch("bedrock_server_manager.web.routers.content.get_settings_instance")
def test_install_addon_api_route_not_found(
    mock_get_settings, mock_isfile, mock_validate_server, client
):
    """Test the install_addon_api_route with a file not found error."""
    mock_validate_server.return_value = True
    mock_isfile.return_value = False
    mock_get_settings.return_value.get.return_value = "/fake/path"

    response = client.post(
        "/api/server/test-server/addon/install",
        json={"filename": "addon.mcaddon"},
    )
    assert response.status_code == 404
    assert "not found for import" in response.json()["detail"]
