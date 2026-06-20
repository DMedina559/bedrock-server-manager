import os
from unittest.mock import MagicMock, patch


def test_get_worlds_list_success(authenticated_client, app_context):
    """Test the get_worlds_list with a successful response."""
    worlds_dir = os.path.join(app_context.settings.get("paths.content"), "worlds")
    os.makedirs(worlds_dir)
    world_file = os.path.join(worlds_dir, "world1.mcworld")
    with open(world_file, "w") as f:
        f.write("test")
    response = authenticated_client.get("/api/content/worlds")
    assert response.status_code == 200
    assert "world1.mcworld" in response.json()["files"][0]


@patch("bedrock_server_manager.web.routers.world.app_api.list_available_worlds_api")
def test_get_worlds_list_failure(mock_list_worlds, authenticated_client):
    """Test the get_worlds_list with a failed response."""
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


def test_post_world_install_success(
    authenticated_client, app_context, real_bedrock_server
):
    """Test the post_world_install with a successful response."""
    worlds_dir = os.path.join(app_context.settings.get("paths.content"), "worlds")
    os.makedirs(worlds_dir, exist_ok=True)
    world_file = os.path.join(worlds_dir, "world.mcworld")
    with open(world_file, "w") as f:
        f.write("test")

    # Mock the task manager's run_task method
    mock_run_task = MagicMock(return_value="test-task-id")
    app_context.task_manager.run_task = mock_run_task

    response = authenticated_client.post(
        f"/api/server/{real_bedrock_server.server_name}/world/install",
        json={"filename": "world.mcworld"},
    )
    assert response.status_code == 202
    json_response = response.json()
    assert "initiated in background" in json_response["message"]
    assert json_response["task_id"] == "test-task-id"

    # Verify that run_task was called
    mock_run_task.assert_called_once()


@patch("bedrock_server_manager.utils.server.validate_server")
@patch("bedrock_server_manager.web.routers.world.os.path.isfile")
def test_post_world_install_not_found(
    mock_isfile, mock_validate_server, authenticated_client
):
    """Test the post_world_install with a file not found error."""
    app_context = MagicMock()
    app_context.settings.get.return_value = "/fake/path"
    authenticated_client.app.state.app_context = app_context
    mock_validate_server.return_value = True
    mock_isfile.return_value = False

    response = authenticated_client.post(
        "/api/server/test-server/world/install",
        json={"filename": "world.mcworld"},
    )
    assert response.status_code == 404
    assert "not found for import" in response.json()["detail"]


def test_post_world_install_queues_task_correctly(
    authenticated_client,
):
    """
    Test that the post_world_install correctly queues a task
    and returns a task ID.
    """
    app_context = authenticated_client.app.state.app_context
    app_context.task_manager.run_task = MagicMock(return_value="test-task-id-123")

    with patch("os.path.isfile", return_value=True):
        # We also need to patch validate_server as it's a dependency
        with patch(
            "bedrock_server_manager.utils.server.validate_server",
            return_value=True,
        ):
            response = authenticated_client.post(
                "/api/server/test-server/world/install",
                json={"filename": "world.mcworld"},
            )

    assert response.status_code == 202
    assert response.json()["task_id"] == "test-task-id-123"
    app_context.task_manager.run_task.assert_called_once()


def test_post_world_export_queues_task_correctly(
    authenticated_client, app_context, real_bedrock_server
):
    """Test the post_world_export correctly queues a task."""
    mock_run_task = MagicMock(return_value="export-task-id")
    app_context.task_manager.run_task = mock_run_task

    response = authenticated_client.post(
        f"/api/server/{real_bedrock_server.server_name}/world/export"
    )

    assert response.status_code == 202
    assert response.json()["task_id"] == "export-task-id"
    mock_run_task.assert_called_once()


def test_delete_world_reset_queues_task_correctly(
    authenticated_client, app_context, real_bedrock_server
):
    """Test the delete_world_reset correctly queues a task."""
    mock_run_task = MagicMock(return_value="reset-task-id")
    app_context.task_manager.run_task = mock_run_task

    response = authenticated_client.delete(
        f"/api/server/{real_bedrock_server.server_name}/world/reset"
    )
    assert response.status_code == 202
    assert response.json()["task_id"] == "reset-task-id"
    mock_run_task.assert_called_once()


def test_serve_world_icon_api_custom(authenticated_client, real_bedrock_server):
    """Test the serve_world_icon_api route with a custom icon."""
    world_name = real_bedrock_server.get_world_name()
    world_dir = os.path.join(real_bedrock_server.server_dir, "worlds", world_name)
    os.makedirs(world_dir, exist_ok=True)
    icon_path = os.path.join(world_dir, "world_icon.jpeg")
    with open(icon_path, "w") as f:
        f.write("fake icon data")

    response = authenticated_client.get(
        f"/api/server/{real_bedrock_server.server_name}/world/icon"
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert response.text == "fake icon data"


@patch("bedrock_server_manager.web.routers.world.os.path.isfile")
def test_serve_world_icon_api_default(
    mock_isfile, authenticated_client, app_context, tmp_path, mocker
):
    """Test the serve_world_icon_api route with a default icon."""
    # Setup mock server to fallback to default
    mock_server = MagicMock()
    mock_server.has_world_icon.return_value = False
    mocker.patch.object(app_context, "get_server", return_value=mock_server)
    mocker.patch("bedrock_server_manager.web.routers.world.STATIC_DIR", str(tmp_path))

    # Create the fake default icon file
    default_icon_dir = tmp_path / "image" / "icon"
    default_icon_dir.mkdir(parents=True)
    (default_icon_dir / "favicon.ico").write_text("fake default icon")

    # Mock isfile to check for custom then default
    mock_isfile.return_value = True

    # Make the request
    response = authenticated_client.get("/api/server/test-server/world/icon")

    # Assert the response
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/vnd.microsoft.icon"
    assert response.text == "fake default icon"


@patch("bedrock_server_manager.web.routers.world.os.path.isfile")
def test_serve_world_icon_api_not_found(
    mock_isfile, authenticated_client, app_context, mocker
):
    """Test the serve_world_icon_api route with no icon found."""
    mock_server = MagicMock()
    mock_server.world_icon_filesystem_path = "/fake/path"
    mock_server.has_world_icon.return_value = False
    mocker.patch.object(app_context, "get_server", return_value=mock_server)
    mock_isfile.return_value = False

    response = authenticated_client.get("/api/server/test-server/world/icon")
    assert response.status_code == 404
