"""
Integration tests for the server_actions router endpoints.
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from bedrock_server_manager.api.models import (
    GetServerSummaryResponse,
    RestartServerResponse,
    SendCommandResponse,
    StartServerResponse,
    StopServerResponse,
)
from bedrock_server_manager.error import (
    BlockedCommandError,
    BSMError,
    ServerNotRunningError,
    ServerStartError,
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
        mock_summary.return_value = GetServerSummaryResponse.model_validate(
            {
                "status": "success",
                "summary": {
                    "name": real_bedrock_server.server_name,
                    "status": "Running",
                    "version": "1.20.10",
                    "player_count": 2,
                    "players": [
                        {"name": "P1", "xuid": "1"},
                        {"name": "P2", "xuid": "2"},
                    ],
                },
            }
        )

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
        mock_summary.side_effect = UserInputError("Could not read status")

        response = admin_auth_client.get(
            f"/api/server/{real_bedrock_server.server_name}/summary"
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.parametrize(
    "action, model, outcome",
    [
        ("start", StartServerResponse, "started"),
        ("start", StartServerResponse, "already_running"),
        ("stop", StopServerResponse, "stopped"),
        ("stop", StopServerResponse, "already_stopped"),
        ("restart", RestartServerResponse, "restarted"),
        ("restart", RestartServerResponse, "started"),
    ],
)
def test_process_lifecycle_returns_completed_result(
    admin_auth_client: TestClient,
    real_bedrock_server,
    app_context,
    action,
    model,
    outcome,
):
    result = model(
        server_name=real_bedrock_server.server_name,
        outcome=outcome,
        message="Completed",
    )
    with (
        patch(
            f"bedrock_server_manager.web.routers.server_actions.server_api.{action}_server",
            return_value=result,
        ) as operation,
        patch("bedrock_server_manager.web.tasks.TaskManager.run_task") as submit,
    ):
        response = admin_auth_client.post(
            f"/api/server/{real_bedrock_server.server_name}/{action}"
        )
        assert response.status_code == 200
        assert response.json() == result.model_dump(mode="json")
        operation.assert_awaited_once()
        assert operation.await_args is not None
        assert (
            operation.await_args.kwargs["request"].server_name
            == real_bedrock_server.server_name
        )
        assert operation.await_args.kwargs["app_context"] is app_context
        submit.assert_not_called()


def test_process_lifecycle_failure_returns_http_error(
    admin_auth_client: TestClient, real_bedrock_server
):
    with patch(
        "bedrock_server_manager.web.routers.server_actions.server_api.start_server",
        side_effect=ServerStartError("Private failure"),
    ) as operation:
        response = admin_auth_client.post(
            f"/api/server/{real_bedrock_server.server_name}/start"
        )
        assert response.status_code == 500
        assert response.json()["error"]["code"] == "server_start_failed"
        assert "Private failure" not in response.text
        operation.assert_awaited_once()


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
        mock_cmd.return_value = SendCommandResponse.model_validate(
            {"status": "success", "message": "Command sent"}
        )

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
    assert "non-empty" in response.json()["error"]["message"]


def test_post_send_command_failed(admin_auth_client: TestClient, real_bedrock_server):
    with patch(
        "bedrock_server_manager.web.routers.server_actions.server_api.send_command"
    ) as mock_cmd:
        mock_cmd.side_effect = UserInputError("Error running command")

        response = admin_auth_client.post(
            f"/api/server/{real_bedrock_server.server_name}/send_command",
            json={"command": "say Hello"},
        )
        assert response.status_code == 400
        assert "Error running command" in response.json()["error"]["message"]


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
        assert "Blocked" in response.json()["error"]["message"]


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
        assert "Offline" in response.json()["error"]["message"]


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
        assert "not found" in response.json()["error"]["message"]


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
        assert response.json()["error"]["message"] == "An unexpected error occurred."


def test_process_lifecycle_openapi_returns_operation_models(test_app):
    schema = test_app.openapi()
    for action in ("start", "stop", "restart"):
        operation = schema["paths"][f"/api/server/{{server_name}}/{action}"]["post"]
        assert "202" not in operation["responses"]
        response = operation["responses"]["200"]["content"]["application/json"][
            "schema"
        ]
        assert (
            response["$ref"] == f"#/components/schemas/{action.title()}ServerResponse"
        )
