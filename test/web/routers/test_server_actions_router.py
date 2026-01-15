from unittest.mock import ANY, patch

from bedrock_server_manager.web.dependencies import validate_server_exists


def test_start_server_route(authenticated_client, real_bedrock_server):
    """Test the start_server_route with a successful response."""
    response = authenticated_client.post(
        f"/api/server/{real_bedrock_server.server_name}/start"
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_stop_server_route(authenticated_client, real_bedrock_server):
    """Test the stop_server_route with a successful response."""
    response = authenticated_client.post(
        f"/api/server/{real_bedrock_server.server_name}/stop"
    )
    assert response.status_code == 202
    assert "initiated in background" in response.json()["message"]


def test_restart_server_route(authenticated_client, real_bedrock_server):
    """Test the restart_server_route with a successful response."""
    response = authenticated_client.post(
        f"/api/server/{real_bedrock_server.server_name}/restart"
    )
    assert response.status_code == 202
    assert "initiated in background" in response.json()["message"]


@patch("bedrock_server_manager.web.routers.server_actions.server_api.send_command")
def test_send_command_route_success(
    mock_send_command, authenticated_client, real_bedrock_server
):
    """Test the send_command_route with a successful response."""
    mock_send_command.return_value = {"status": "success"}
    response = authenticated_client.post(
        f"/api/server/{real_bedrock_server.server_name}/send_command",
        json={"command": "list"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    mock_send_command.assert_called_once_with(
        server_name=real_bedrock_server.server_name, command="list", app_context=ANY
    )


@patch("bedrock_server_manager.web.routers.server_actions.server_api.send_command")
def test_send_command_route_blocked_command(mock_send_command, authenticated_client):
    """Test the send_command_route with a blocked command."""
    authenticated_client.app.dependency_overrides[validate_server_exists] = (
        lambda: "test-server"
    )
    from bedrock_server_manager.error import BlockedCommandError

    mock_send_command.side_effect = BlockedCommandError("Command is blocked")
    response = authenticated_client.post(
        "/api/server/test-server/send_command", json={"command": "stop"}
    )
    assert response.status_code == 403
    assert "Command is blocked" in response.json()["detail"]
    authenticated_client.app.dependency_overrides.clear()


@patch("bedrock_server_manager.web.routers.server_actions.server_api.send_command")
def test_send_command_route_server_not_running(mock_send_command, authenticated_client):
    """Test the send_command_route with a server that is not running."""
    authenticated_client.app.dependency_overrides[validate_server_exists] = (
        lambda: "test-server"
    )
    from bedrock_server_manager.error import ServerNotRunningError

    mock_send_command.side_effect = ServerNotRunningError("Server is not running")
    response = authenticated_client.post(
        "/api/server/test-server/send_command", json={"command": "list"}
    )
    assert response.status_code == 409
    assert "Server is not running" in response.json()["detail"]
    authenticated_client.app.dependency_overrides.clear()


@patch("bedrock_server_manager.web.routers.server_actions.server_api.send_command")
def test_send_command_route_user_input_error(mock_send_command, authenticated_client):
    """Test the send_command_route with a UserInputError."""
    authenticated_client.app.dependency_overrides[validate_server_exists] = (
        lambda: "test-server"
    )
    from bedrock_server_manager.error import UserInputError

    mock_send_command.side_effect = UserInputError("Invalid command")
    response = authenticated_client.post(
        "/api/server/test-server/send_command", json={"command": "invalid"}
    )
    assert response.status_code == 400
    assert "Invalid command" in response.json()["detail"]
    authenticated_client.app.dependency_overrides.clear()


@patch("bedrock_server_manager.web.routers.server_actions.server_api.send_command")
def test_send_command_route_bsm_error(mock_send_command, authenticated_client):
    """Test the send_command_route with a BSMError."""
    authenticated_client.app.dependency_overrides[validate_server_exists] = (
        lambda: "test-server"
    )
    from bedrock_server_manager.error import BSMError

    mock_send_command.side_effect = BSMError("Failed to send command")
    response = authenticated_client.post(
        "/api/server/test-server/send_command", json={"command": "list"}
    )
    assert response.status_code == 500
    assert "Failed to send command" in response.json()["detail"]
    authenticated_client.app.dependency_overrides.clear()


def test_update_server_route(authenticated_client, real_bedrock_server):
    """Test the update_server_route with a successful response."""
    response = authenticated_client.post(
        f"/api/server/{real_bedrock_server.server_name}/update"
    )
    assert response.status_code == 202
    assert "initiated in background" in response.json()["message"]


def test_delete_server_route(authenticated_client, real_bedrock_server):
    """Test the delete_server_route with a successful response."""
    response = authenticated_client.delete(
        f"/api/server/{real_bedrock_server.server_name}/delete"
    )
    assert response.status_code == 202
    assert "initiated in background" in response.json()["message"]
