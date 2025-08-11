from unittest.mock import patch, MagicMock
import pytest


@patch("bedrock_server_manager.web.routers.content.app_api.list_available_worlds_api")
def test_list_worlds_api_route_success(mock_list_worlds, authenticated_client):
    """Test the list_worlds_api_route with a successful response."""
    app_context = MagicMock()
    authenticated_client.app.state.app_context = app_context
    mock_list_worlds.return_value = {
        "status": "success",
        "files": ["world1.mcworld", "world2.mcworld"],
    }
    response = authenticated_client.get("/api/content/worlds")
    assert response.status_code == 200
    assert response.json()["files"] == ["world1.mcworld", "world2.mcworld"]
    mock_list_worlds.assert_called_once_with(app_context=app_context)


@patch("bedrock_server_manager.web.routers.content.app_api.list_available_worlds_api")
def test_list_worlds_api_route_failure(mock_list_worlds, authenticated_client):
    """Test the list_worlds_api_route with a failed response."""
    app_context = MagicMock()
    authenticated_client.app.state.app_context = app_context
    mock_list_worlds.return_value = {
        "status": "error",
        "message": "Failed to list worlds",
    }
    response = authenticated_client.get("/api/content/worlds")
    assert response.status_code == 500
    assert (
        "A critical server error occurred while listing worlds."
        in response.json()["detail"]
    )


@patch("bedrock_server_manager.web.routers.content.app_api.list_available_addons_api")
def test_list_addons_api_route_success(mock_list_addons, authenticated_client):
    """Test the list_addons_api_route with a successful response."""
    app_context = MagicMock()
    authenticated_client.app.state.app_context = app_context
    mock_list_addons.return_value = {
        "status": "success",
        "files": ["addon1.mcaddon", "addon2.mcpack"],
    }
    response = authenticated_client.get("/api/content/addons")
    assert response.status_code == 200
    assert response.json()["files"] == ["addon1.mcaddon", "addon2.mcpack"]
    mock_list_addons.assert_called_once_with(app_context=app_context)


@patch("bedrock_server_manager.web.routers.content.app_api.list_available_addons_api")
def test_list_addons_api_route_failure(mock_list_addons, authenticated_client):
    """Test the list_addons_api_route with a failed response."""
    app_context = MagicMock()
    authenticated_client.app.state.app_context = app_context
    mock_list_addons.return_value = {
        "status": "error",
        "message": "Failed to list addons",
    }
    response = authenticated_client.get("/api/content/addons")
    assert response.status_code == 500
    assert (
        "A critical server error occurred while listing addons."
        in response.json()["detail"]
    )


@patch("bedrock_server_manager.web.routers.content.utils_api.validate_server_exist")
@patch("bedrock_server_manager.web.routers.content.os.path.isfile")
def test_install_world_api_route_success(
    mock_isfile, mock_validate_server, authenticated_client
):
    """Test the install_world_api_route with a successful response."""
    app_context = MagicMock()
    app_context.settings.get.return_value = "/fake/path"
    authenticated_client.app.state.app_context = app_context
    mock_validate_server.return_value = {"status": "success"}
    mock_isfile.return_value = True

    response = authenticated_client.post(
        "/api/server/test-server/world/install",
        json={"filename": "world.mcworld"},
    )
    assert response.status_code == 202
    assert "initiated in background" in response.json()["message"]


@patch("bedrock_server_manager.web.routers.content.utils_api.validate_server_exist")
@patch("bedrock_server_manager.web.routers.content.os.path.isfile")
def test_install_world_api_route_not_found(
    mock_isfile, mock_validate_server, authenticated_client
):
    """Test the install_world_api_route with a file not found error."""
    app_context = MagicMock()
    app_context.settings.get.return_value = "/fake/path"
    authenticated_client.app.state.app_context = app_context
    mock_validate_server.return_value = {"status": "success"}
    mock_isfile.return_value = False

    response = authenticated_client.post(
        "/api/server/test-server/world/install",
        json={"filename": "world.mcworld"},
    )
    assert response.status_code == 404
    assert "not found for import" in response.json()["detail"]


@patch("bedrock_server_manager.web.routers.content.world_api.import_world")
def test_install_world_api_route_user_input_error(
    mock_import_world, authenticated_client, caplog
):
    """Test the install_world_api_route with a UserInputError."""
    from bedrock_server_manager.error import UserInputError

    app_context = MagicMock()
    app_context.settings.get.return_value = "/fake/path"
    authenticated_client.app.state.app_context = app_context
    mock_import_world.side_effect = UserInputError("Invalid world file")
    with patch("os.path.isfile", return_value=True):
        response = authenticated_client.post(
            "/api/server/test-server/world/install",
            json={"filename": "world.mcworld"},
        )
    assert response.status_code == 202
    assert "Invalid world file" in caplog.text


@patch("bedrock_server_manager.web.routers.content.world_api.import_world")
def test_install_world_api_route_bsm_error(
    mock_import_world, authenticated_client, caplog
):
    """Test the install_world_api_route with a BSMError."""
    from bedrock_server_manager.error import BSMError

    app_context = MagicMock()
    app_context.settings.get.return_value = "/fake/path"
    authenticated_client.app.state.app_context = app_context
    mock_import_world.side_effect = BSMError("Failed to import world")
    with patch("os.path.isfile", return_value=True):
        response = authenticated_client.post(
            "/api/server/test-server/world/install",
            json={"filename": "world.mcworld"},
        )
    assert response.status_code == 202
    assert "Failed to import world" in caplog.text


@patch("bedrock_server_manager.web.routers.content.world_api.export_world")
def test_export_world_api_route_user_input_error(
    mock_export_world, authenticated_client, caplog
):
    """Test the export_world_api_route with a UserInputError."""
    from bedrock_server_manager.error import UserInputError

    app_context = MagicMock()
    authenticated_client.app.state.app_context = app_context
    mock_export_world.side_effect = UserInputError("Invalid server name")
    response = authenticated_client.post("/api/server/test-server/world/export")
    assert response.status_code == 202
    assert "Invalid server name" in caplog.text


@patch("bedrock_server_manager.web.routers.content.world_api.export_world")
def test_export_world_api_route_bsm_error(
    mock_export_world, authenticated_client, caplog
):
    """Test the export_world_api_route with a BSMError."""
    from bedrock_server_manager.error import BSMError

    app_context = MagicMock()
    authenticated_client.app.state.app_context = app_context
    mock_export_world.side_effect = BSMError("Failed to export world")
    response = authenticated_client.post("/api/server/test-server/world/export")
    assert response.status_code == 202
    assert "Failed to export world" in caplog.text


@patch("bedrock_server_manager.web.routers.content.world_api.reset_world")
def test_reset_world_api_route_user_input_error(
    mock_reset_world, authenticated_client, caplog
):
    """Test the reset_world_api_route with a UserInputError."""
    from bedrock_server_manager.error import UserInputError

    app_context = MagicMock()
    authenticated_client.app.state.app_context = app_context
    mock_reset_world.side_effect = UserInputError("Invalid server name")
    response = authenticated_client.delete("/api/server/test-server/world/reset")
    assert response.status_code == 202
    assert "Invalid server name" in caplog.text


@patch("bedrock_server_manager.web.routers.content.world_api.reset_world")
def test_reset_world_api_route_bsm_error(
    mock_reset_world, authenticated_client, caplog
):
    """Test the reset_world_api_route with a BSMError."""
    from bedrock_server_manager.error import BSMError

    app_context = MagicMock()
    authenticated_client.app.state.app_context = app_context
    mock_reset_world.side_effect = BSMError("Failed to reset world")
    response = authenticated_client.delete("/api/server/test-server/world/reset")
    assert response.status_code == 202
    assert "Failed to reset world" in caplog.text


@patch("bedrock_server_manager.web.routers.content.addon_api.import_addon")
def test_install_addon_api_route_user_input_error(
    mock_import_addon, authenticated_client, caplog
):
    """Test the install_addon_api_route with a UserInputError."""
    from bedrock_server_manager.error import UserInputError

    app_context = MagicMock()
    app_context.settings.get.return_value = "/fake/path"
    authenticated_client.app.state.app_context = app_context
    mock_import_addon.side_effect = UserInputError("Invalid addon file")
    with patch("os.path.isfile", return_value=True):
        response = authenticated_client.post(
            "/api/server/test-server/addon/install",
            json={"filename": "addon.mcaddon"},
        )
    assert response.status_code == 202
    assert "Invalid addon file" in caplog.text


@patch("bedrock_server_manager.web.routers.content.addon_api.import_addon")
def test_install_addon_api_route_bsm_error(
    mock_import_addon, authenticated_client, caplog
):
    """Test the install_addon_api_route with a BSMError."""
    from bedrock_server_manager.error import BSMError

    app_context = MagicMock()
    app_context.settings.get.return_value = "/fake/path"
    authenticated_client.app.state.app_context = app_context
    mock_import_addon.side_effect = BSMError("Failed to import addon")
    with patch("os.path.isfile", return_value=True):
        response = authenticated_client.post(
            "/api/server/test-server/addon/install",
            json={"filename": " addon.mcaddon"},
        )
    assert response.status_code == 202
    assert "Failed to import addon" in caplog.text


@patch("bedrock_server_manager.web.routers.content.utils_api.validate_server_exist")
def test_export_world_api_route_success(mock_validate_server, authenticated_client):
    """Test the export_world_api_route with a successful response."""
    app_context = MagicMock()
    authenticated_client.app.state.app_context = app_context
    mock_validate_server.return_value = {"status": "success"}

    response = authenticated_client.post("/api/server/test-server/world/export")
    assert response.status_code == 202
    assert "initiated in background" in response.json()["message"]


@patch("bedrock_server_manager.web.routers.content.utils_api.validate_server_exist")
def test_reset_world_api_route_success(mock_validate_server, authenticated_client):
    """Test the reset_world_api_route with a successful response."""
    app_context = MagicMock()
    authenticated_client.app.state.app_context = app_context
    mock_validate_server.return_value = {"status": "success"}

    response = authenticated_client.delete("/api/server/test-server/world/reset")
    assert response.status_code == 202
    assert "initiated in background" in response.json()["message"]


@patch("bedrock_server_manager.web.routers.content.utils_api.validate_server_exist")
@patch("bedrock_server_manager.web.routers.content.os.path.isfile")
def test_install_addon_api_route_success(
    mock_isfile, mock_validate_server, authenticated_client
):
    """Test the install_addon_api_route with a successful response."""
    app_context = MagicMock()
    app_context.settings.get.return_value = "/fake/path"
    authenticated_client.app.state.app_context = app_context
    mock_validate_server.return_value = {"status": "success"}
    mock_isfile.return_value = True

    response = authenticated_client.post(
        "/api/server/test-server/addon/install",
        json={"filename": "addon.mcaddon"},
    )
    assert response.status_code == 202
    assert "initiated in background" in response.json()["message"]


@patch("bedrock_server_manager.web.routers.content.utils_api.validate_server_exist")
@patch("bedrock_server_manager.web.routers.content.os.path.isfile")
def test_install_addon_api_route_not_found(
    mock_isfile, mock_validate_server, authenticated_client
):
    """Test the install_addon_api_route with a file not found error."""
    app_context = MagicMock()
    app_context.settings.get.return_value = "/fake/path"
    authenticated_client.app.state.app_context = app_context
    mock_validate_server.return_value = {"status": "success"}
    mock_isfile.return_value = False

    response = authenticated_client.post(
        "/api/server/test-server/addon/install",
        json={"filename": "addon.mcaddon"},
    )
    assert response.status_code == 404
    assert "not found for import" in response.json()["detail"]
