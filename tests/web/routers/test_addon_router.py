import os
from unittest.mock import MagicMock, patch


def test_get_addons_success(authenticated_client, app_context):
    """Test the get_addons with a successful response."""
    addons_dir = os.path.join(app_context.settings.get("paths.content"), "addons")
    os.makedirs(addons_dir)
    addon_file = os.path.join(addons_dir, "addon1.mcaddon")
    with open(addon_file, "w") as f:
        f.write("test")
    response = authenticated_client.get("/api/content/addons")
    assert response.status_code == 200
    assert "addon1.mcaddon" in response.json()["files"][0]


@patch("bedrock_server_manager.web.routers.addon.addon_api.list_available_addons")
def test_get_addons_failure(mock_list_addons, authenticated_client):
    """Test the get_addons with a failed response."""
    app_context = MagicMock()
    authenticated_client.app.state.app_context = app_context
    mock_list_addons.return_value = {
        "status": "error",
        "message": "Failed to list addons",
    }
    response = authenticated_client.get("/api/content/addons")
    assert response.status_code == 500


def test_post_install_addon_queues_task_correctly(
    authenticated_client, app_context, real_bedrock_server
):
    """Test the install_addon_api_route correctly queues a task."""
    addons_dir = os.path.join(app_context.settings.get("paths.content"), "addons")
    os.makedirs(addons_dir, exist_ok=True)
    addon_file = os.path.join(addons_dir, "addon.mcaddon")
    with open(addon_file, "w") as f:
        f.write("test")

    mock_run_task = MagicMock(return_value="addon-task-id")
    app_context.task_manager.run_task = mock_run_task

    response = authenticated_client.post(
        f"/api/server/{real_bedrock_server.server_name}/addon/install",
        json={"filename": "addon.mcaddon"},
    )
    assert response.status_code == 202
    assert response.json()["task_id"] == "addon-task-id"
    mock_run_task.assert_called_once()


@patch("bedrock_server_manager.utils.server.validate_server")
@patch("bedrock_server_manager.web.routers.addon.os.path.isfile")
def test_post_install_addon_not_found(
    mock_isfile, mock_validate_server, authenticated_client
):
    """Test the install_addon_api_route with a file not found error."""
    app_context = MagicMock()
    app_context.settings.get.return_value = "/fake/path"
    authenticated_client.app.state.app_context = app_context
    mock_validate_server.return_value = True
    mock_isfile.return_value = False

    response = authenticated_client.post(
        "/api/server/test-server/addon/install",
        json={"filename": "addon.mcaddon"},
    )
    assert response.status_code == 404
    assert "not found for import" in response.json()["detail"]
