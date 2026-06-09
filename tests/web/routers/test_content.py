import os
from unittest.mock import MagicMock, patch


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


def test_install_world_api_route_success(
    authenticated_client, app_context, real_bedrock_server
):
    """Test the install_world_api_route with a successful response."""
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
@patch("bedrock_server_manager.web.routers.content.os.path.isfile")
def test_install_world_api_route_not_found(
    mock_isfile, mock_validate_server, authenticated_client
):
    """Test the install_world_api_route with a file not found error."""
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


def test_install_world_api_route_queues_task_correctly(
    authenticated_client,
):
    """
    Test that the install_world_api_route correctly queues a task
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


def test_export_world_api_route_queues_task_correctly(
    authenticated_client, app_context, real_bedrock_server
):
    """Test the export_world_api_route correctly queues a task."""
    mock_run_task = MagicMock(return_value="export-task-id")
    app_context.task_manager.run_task = mock_run_task

    response = authenticated_client.post(
        f"/api/server/{real_bedrock_server.server_name}/world/export"
    )

    assert response.status_code == 202
    assert response.json()["task_id"] == "export-task-id"
    mock_run_task.assert_called_once()


def test_reset_world_api_route_queues_task_correctly(
    authenticated_client, app_context, real_bedrock_server
):
    """Test the reset_world_api_route correctly queues a task."""
    mock_run_task = MagicMock(return_value="reset-task-id")
    app_context.task_manager.run_task = mock_run_task

    response = authenticated_client.delete(
        f"/api/server/{real_bedrock_server.server_name}/world/reset"
    )
    assert response.status_code == 202
    assert response.json()["task_id"] == "reset-task-id"
    mock_run_task.assert_called_once()
