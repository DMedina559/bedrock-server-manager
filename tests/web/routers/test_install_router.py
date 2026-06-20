import os
from unittest.mock import MagicMock, patch


def test_get_custom_zips(authenticated_client, app_context):
    """Test the get_custom_zips route with a successful response."""
    custom_dir = os.path.join(app_context.settings.get("paths.downloads"), "custom")
    os.makedirs(custom_dir, exist_ok=True)
    zip_file = os.path.join(custom_dir, "zip1.zip")
    with open(zip_file, "w") as f:
        f.write("test")

    response = authenticated_client.get("/api/downloads/list")
    assert response.status_code == 200
    assert "zip1.zip" in response.json()["custom_zips"]


def test_post_install_server_success(authenticated_client):
    """Test the install_server_api_route with a successful installation."""
    app_context = authenticated_client.app.state.app_context
    app_context.task_manager.run_task = MagicMock(return_value="install-task-id")

    # Mock the utils functions that are called before the task is created
    with patch(
        "bedrock_server_manager.utils.server.core_validate_server_name_format",
        return_value=None,
    ):
        with patch(
            "bedrock_server_manager.utils.server.validate_server",
            return_value=False,
        ):
            response = authenticated_client.post(
                "/api/server/install",
                json={"server_name": "new-server", "server_version": "LATEST"},
            )

    assert response.status_code == 200
    json_data = response.json()
    assert json_data["status"] == "pending"
    assert json_data["task_id"] == "install-task-id"
    app_context.task_manager.run_task.assert_called_once()


@patch("bedrock_server_manager.utils.server.validate_server")
@patch("bedrock_server_manager.utils.server.core_validate_server_name_format")
def test_post_install_server_confirmation_needed(
    mock_validate_name, mock_validate_exist, authenticated_client
):
    """Test the install_server_api_route when confirmation is needed."""
    mock_validate_name.return_value = None
    mock_validate_exist.return_value = True

    response = authenticated_client.post(
        "/api/server/install",
        json={"server_name": "existing-server", "server_version": "LATEST"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "confirm_needed"


@patch("bedrock_server_manager.utils.server.core_validate_server_name_format")
def test_post_install_server_invalid_name(mock_validate_name, authenticated_client):
    from bedrock_server_manager.error import UserInputError

    """Test the install_server_api_route with an invalid server name."""
    mock_validate_name.side_effect = UserInputError("Invalid server name.")

    response = authenticated_client.post(
        "/api/server/install",
        json={"server_name": "invalid name", "server_version": "LATEST"},
    )
    assert response.status_code == 400
    assert "Invalid server name" in response.json()["detail"]
