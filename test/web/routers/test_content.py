from unittest.mock import patch, MagicMock
import pytest


import os


def test_list_worlds_api_route_success(authenticated_client, app_context):
    """Test the list_worlds_api_route with a successful response."""
    worlds_dir = os.path.join(app_context.settings.get("paths.content"), "worlds")
    os.makedirs(worlds_dir)
    world_file = os.path.join(worlds_dir, "world1.mcworld")
    with open(world_file, "w") as f:
        f.write("test")
    response = authenticated_client.get("/api/content/worlds")
    assert response.status_code == 200
    assert "world1.mcworld" in response.json()["files"][0]


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


def test_list_addons_api_route_success(authenticated_client, app_context):
    """Test the list_addons_api_route with a successful response."""
    addons_dir = os.path.join(app_context.settings.get("paths.content"), "addons")
    os.makedirs(addons_dir)
    addon_file = os.path.join(addons_dir, "addon1.mcaddon")
    with open(addon_file, "w") as f:
        f.write("test")
    response = authenticated_client.get("/api/content/addons")
    assert response.status_code == 200
    assert "addon1.mcaddon" in response.json()["files"][0]


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


def test_install_world_api_route_success(
    authenticated_client, app_context, real_bedrock_server
):
    """Test the install_world_api_route with a successful response."""
    worlds_dir = os.path.join(app_context.settings.get("paths.content"), "worlds")
    os.makedirs(worlds_dir)
    world_file = os.path.join(worlds_dir, "world.mcworld")
    with open(world_file, "w") as f:
        f.write("test")

    response = authenticated_client.post(
        f"/api/server/{real_bedrock_server.server_name}/world/install",
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


def test_export_world_api_route_success(
    authenticated_client, app_context, real_bedrock_server
):
    """Test the export_world_api_route with a successful response."""
    response = authenticated_client.post(
        f"/api/server/{real_bedrock_server.server_name}/world/export"
    )
    assert response.status_code == 202
    assert "initiated in background" in response.json()["message"]


def test_reset_world_api_route_success(
    authenticated_client, app_context, real_bedrock_server
):
    """Test the reset_world_api_route with a successful response."""
    response = authenticated_client.delete(
        f"/api/server/{real_bedrock_server.server_name}/world/reset"
    )
    assert response.status_code == 202
    assert "initiated in background" in response.json()["message"]


def test_install_addon_api_route_success(
    authenticated_client, app_context, real_bedrock_server
):
    """Test the install_addon_api_route with a successful response."""
    addons_dir = os.path.join(app_context.settings.get("paths.content"), "addons")
    os.makedirs(addons_dir)
    addon_file = os.path.join(addons_dir, "addon.mcaddon")
    with open(addon_file, "w") as f:
        f.write("test")

    response = authenticated_client.post(
        f"/api/server/{real_bedrock_server.server_name}/addon/install",
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
