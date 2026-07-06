"""
Integration tests for the server_actions router endpoints.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient

from bedrock_server_manager.error import (
    BlockedCommandError,
    BSMError,
    ServerNotRunningError,
    UserInputError,
)


def test_get_server_summary_unauthorized(
    unauth_client: TestClient, real_bedrock_server
):
    response = unauth_client.get(
        f"/api/server/{real_bedrock_server.server_name}/summary"
    )
    assert response.status_code == 401


def test_get_server_summary_success(admin_auth_client: TestClient, real_bedrock_server):
    with patch(
        "bedrock_server_manager.web.routers.server_actions.server_api.get_server_summary"
    ) as mock_summary:
        mock_summary.return_value = {
            "status": "success",
            "summary": {
                "name": real_bedrock_server.server_name,
                "status": "Running",
                "version": "1.20.10",
                "player_count": 2,
                "players": [{"name": "P1"}, {"name": "P2"}],
            },
        }

        response = admin_auth_client.get(
            f"/api/server/{real_bedrock_server.server_name}/summary"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == real_bedrock_server.server_name
        assert data["status"] == "Running"
        assert data["player_count"] == 2


def test_get_server_summary_error(admin_auth_client: TestClient, real_bedrock_server):
    with patch(
        "bedrock_server_manager.web.routers.server_actions.server_api.get_server_summary"
    ) as mock_summary:
        mock_summary.return_value = {
            "status": "error",
            "message": "Could not read status",
        }

        response = admin_auth_client.get(
            f"/api/server/{real_bedrock_server.server_name}/summary"
        )
        assert response.status_code == 400
        assert "Could not read status" in response.json()["detail"]


def test_post_start_server(admin_auth_client: TestClient, real_bedrock_server):
    with patch(
        "bedrock_server_manager.web.tasks.TaskManager.run_task",
        return_value="task-start",
    ):
        response = admin_auth_client.post(
            f"/api/server/{real_bedrock_server.server_name}/start"
        )
        assert response.status_code == 202
        assert response.json()["task_id"] == "task-start"


def test_post_stop_server(admin_auth_client: TestClient, real_bedrock_server):
    with patch(
        "bedrock_server_manager.web.tasks.TaskManager.run_task",
        return_value="task-stop",
    ):
        response = admin_auth_client.post(
            f"/api/server/{real_bedrock_server.server_name}/stop"
        )
        assert response.status_code == 202
        assert response.json()["task_id"] == "task-stop"


def test_post_restart_server(admin_auth_client: TestClient, real_bedrock_server):
    with patch(
        "bedrock_server_manager.web.tasks.TaskManager.run_task",
        return_value="task-restart",
    ):
        response = admin_auth_client.post(
            f"/api/server/{real_bedrock_server.server_name}/restart"
        )
        assert response.status_code == 202
        assert response.json()["task_id"] == "task-restart"


def test_post_update_server(admin_auth_client: TestClient, real_bedrock_server):
    with patch(
        "bedrock_server_manager.web.tasks.TaskManager.run_task",
        return_value="task-update",
    ):
        response = admin_auth_client.post(
            f"/api/server/{real_bedrock_server.server_name}/update"
        )
        assert response.status_code == 202
        assert response.json()["task_id"] == "task-update"


def test_delete_server(admin_auth_client: TestClient, real_bedrock_server):
    with patch(
        "bedrock_server_manager.web.tasks.TaskManager.run_task",
        return_value="task-delete",
    ):

        response = admin_auth_client.request(
            "DELETE", f"/api/server/{real_bedrock_server.server_name}/delete"
        )
        assert response.status_code == 202
        assert response.json()["task_id"] == "task-delete"


def test_post_send_command_success(admin_auth_client: TestClient, real_bedrock_server):
    with patch(
        "bedrock_server_manager.web.routers.server_actions.server_api.send_command"
    ) as mock_cmd:
        mock_cmd.return_value = {
            "status": "success",
            "message": "Command sent",
            "details": "Success",
        }

        response = admin_auth_client.post(
            f"/api/server/{real_bedrock_server.server_name}/send_command",
            json={"command": "say Hello"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "success"


def test_post_send_command_empty(admin_auth_client: TestClient, real_bedrock_server):
    response = admin_auth_client.post(
        f"/api/server/{real_bedrock_server.server_name}/send_command",
        json={"command": "   "},
    )
    assert response.status_code == 400
    assert "non-empty" in response.json()["detail"]


def test_post_send_command_failed(admin_auth_client: TestClient, real_bedrock_server):
    with patch(
        "bedrock_server_manager.web.routers.server_actions.server_api.send_command"
    ) as mock_cmd:
        mock_cmd.return_value = {"status": "error", "message": "Error running command"}

        response = admin_auth_client.post(
            f"/api/server/{real_bedrock_server.server_name}/send_command",
            json={"command": "say Hello"},
        )
        assert response.status_code == 400
        assert "Error running command" in response.json()["detail"]


def test_post_send_command_blocked(admin_auth_client: TestClient, real_bedrock_server):
    with patch(
        "bedrock_server_manager.web.routers.server_actions.server_api.send_command"
    ) as mock_cmd:
        mock_cmd.side_effect = BlockedCommandError("Blocked")

        response = admin_auth_client.post(
            f"/api/server/{real_bedrock_server.server_name}/send_command",
            json={"command": "stop"},
        )
        assert response.status_code == 403
        assert "Blocked" in response.json()["detail"]


def test_post_send_command_not_running(
    admin_auth_client: TestClient, real_bedrock_server
):
    with patch(
        "bedrock_server_manager.web.routers.server_actions.server_api.send_command"
    ) as mock_cmd:
        mock_cmd.side_effect = ServerNotRunningError("Offline")

        response = admin_auth_client.post(
            f"/api/server/{real_bedrock_server.server_name}/send_command",
            json={"command": "say Hello"},
        )
        assert response.status_code == 409
        assert "Offline" in response.json()["detail"]


def test_post_send_command_not_found(
    admin_auth_client: TestClient, real_bedrock_server
):
    with patch(
        "bedrock_server_manager.web.routers.server_actions.server_api.send_command"
    ) as mock_cmd:
        mock_cmd.side_effect = UserInputError("Server not found")

        response = admin_auth_client.post(
            f"/api/server/{real_bedrock_server.server_name}/send_command",
            json={"command": "say Hello"},
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]


def test_post_send_command_bsm_error(
    admin_auth_client: TestClient, real_bedrock_server
):
    with patch(
        "bedrock_server_manager.web.routers.server_actions.server_api.send_command"
    ) as mock_cmd:
        mock_cmd.side_effect = BSMError("Unknown BSM issue")

        response = admin_auth_client.post(
            f"/api/server/{real_bedrock_server.server_name}/send_command",
            json={"command": "say Hello"},
        )
        assert response.status_code == 500
        assert "Unknown BSM issue" in response.json()["detail"]
