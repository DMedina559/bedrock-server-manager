"""
Integration tests for the permissions router endpoints.
"""

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from bedrock_server_manager.api.models import (
    GetPermissionsResponse,
    SetPermissionsResponse,
)
from bedrock_server_manager.error import AppFileNotFoundError, BSMError, UserInputError


def test_post_permissions_set_unauthorized(
    unauth_client: TestClient, real_bedrock_server
):
    response = unauth_client.post(
        f"/api/server/{real_bedrock_server.server_name}/permissions/set",
        json={
            "permissions": [
                {"xuid": "123", "name": "Player1", "permission_level": "operator"}
            ]
        },
    )
    assert response.status_code == 401


def test_post_permissions_set_forbidden(auth_client: TestClient, real_bedrock_server):
    response = auth_client.post(
        f"/api/server/{real_bedrock_server.server_name}/permissions/set",
        json={
            "permissions": [
                {"xuid": "123", "name": "Player1", "permission_level": "operator"}
            ]
        },
    )
    assert response.status_code == 403


def test_post_permissions_set_success(
    admin_auth_client: TestClient, real_bedrock_server
):
    with patch(
        "bedrock_server_manager.web.routers.permissions.permissions_api.set_permissions",
        new_callable=AsyncMock,
    ) as mock_set:
        mock_set.return_value = SetPermissionsResponse.model_validate(
            {"status": "success", "message": "Completed successfully."}
        )

        response = admin_auth_client.post(
            f"/api/server/{real_bedrock_server.server_name}/permissions/set",
            json={
                "permissions": [
                    {"xuid": "123", "name": "Player1", "permission_level": "operator"}
                ]
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "1 player(s)" in data["message"]
        mock_set.assert_called_once()


def test_post_permissions_set_partial_failure(
    admin_auth_client: TestClient, real_bedrock_server
):
    with patch(
        "bedrock_server_manager.web.routers.permissions.permissions_api.set_permissions",
        new_callable=AsyncMock,
    ) as mock_set:
        # Mock side effect to succeed for first, fail for second
        async def side_effect(request, **kwargs):
            if request.xuid == "123":
                return SetPermissionsResponse(message="Permission set.")
            raise BSMError("Failed to set")

        mock_set.side_effect = side_effect

        response = admin_auth_client.post(
            f"/api/server/{real_bedrock_server.server_name}/permissions/set",
            json={
                "permissions": [
                    {"xuid": "123", "name": "Player1", "permission_level": "operator"},
                    {"xuid": "456", "name": "Player2", "permission_level": "member"},
                ]
            },
        )

        assert response.status_code == 500
        data = response.json()
        assert data["error"]["code"] == "internal_error"
        assert "Errors occurred" in data["error"]["message"]
        assert "456" in data["error"]["details"]["errors"]
        assert (
            data["error"]["details"]["errors"]["456"]
            == "The application operation failed."
        )


def test_post_permissions_set_not_found_error(
    admin_auth_client: TestClient, real_bedrock_server
):
    with patch(
        "bedrock_server_manager.web.routers.permissions.permissions_api.set_permissions",
        new_callable=AsyncMock,
    ) as mock_set:
        mock_set.side_effect = AppFileNotFoundError("Player not found")

        response = admin_auth_client.post(
            f"/api/server/{real_bedrock_server.server_name}/permissions/set",
            json={
                "permissions": [
                    {"xuid": "123", "name": "Player1", "permission_level": "operator"}
                ]
            },
        )

        assert response.status_code == 404
        data = response.json()
        assert data["error"]["details"]["errors"]["123"] == "Resource not found."


def test_post_permissions_set_exception(
    admin_auth_client: TestClient, real_bedrock_server
):
    with patch(
        "bedrock_server_manager.web.routers.permissions.permissions_api.set_permissions",
        new_callable=AsyncMock,
    ) as mock_set:
        mock_set.side_effect = Exception("Crash")

        response = admin_auth_client.post(
            f"/api/server/{real_bedrock_server.server_name}/permissions/set",
            json={
                "permissions": [
                    {"xuid": "123", "name": "Player1", "permission_level": "operator"}
                ]
            },
        )

        assert response.status_code == 500
        data = response.json()
        assert (
            data["error"]["details"]["errors"]["123"] == "An unexpected error occurred."
        )


def test_post_permissions_set_bsm_error(
    admin_auth_client: TestClient, real_bedrock_server
):
    with patch(
        "bedrock_server_manager.web.routers.permissions.permissions_api.set_permissions",
        new_callable=AsyncMock,
    ) as mock_set:
        mock_set.side_effect = BSMError("BSMError: Config corrupted")

        response = admin_auth_client.post(
            f"/api/server/{real_bedrock_server.server_name}/permissions/set",
            json={
                "permissions": [
                    {"xuid": "123", "name": "Player1", "permission_level": "operator"}
                ]
            },
        )

        assert response.status_code == 500
        data = response.json()
        assert (
            data["error"]["details"]["errors"]["123"]
            == "The application operation failed."
        )


def test_post_permissions_set_user_input_error(
    admin_auth_client: TestClient, real_bedrock_server
):
    with patch(
        "bedrock_server_manager.web.routers.permissions.permissions_api.set_permissions",
        new_callable=AsyncMock,
    ) as mock_set:
        mock_set.side_effect = UserInputError("Invalid permission level")

        response = admin_auth_client.post(
            f"/api/server/{real_bedrock_server.server_name}/permissions/set",
            json={
                "permissions": [
                    {"xuid": "123", "name": "Player1", "permission_level": "invalid"}
                ]
            },
        )

        assert response.status_code == 400
        data = response.json()
        assert (
            data["error"]["details"]["errors"]["123"] == "API data failed validation."
        )


def test_get_permissions_unauthorized(unauth_client: TestClient, real_bedrock_server):
    response = unauth_client.get(
        f"/api/server/{real_bedrock_server.server_name}/permissions/get"
    )
    assert response.status_code == 401


def test_get_permissions_success(admin_auth_client: TestClient, real_bedrock_server):
    with patch(
        "bedrock_server_manager.web.routers.permissions.permissions_api.get_permissions",
        new_callable=AsyncMock,
    ) as mock_get:
        mock_get.return_value = GetPermissionsResponse.model_validate(
            {
                "status": "success",
                "permissions": [
                    {"xuid": "123", "name": "Player1", "permission_level": "operator"}
                ],
            }
        )

        response = admin_auth_client.get(
            f"/api/server/{real_bedrock_server.server_name}/permissions/get"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert len(data["permissions"]) == 1
        assert data["permissions"][0]["name"] == "Player1"


def test_get_permissions_not_found(admin_auth_client: TestClient, real_bedrock_server):
    with patch(
        "bedrock_server_manager.web.routers.permissions.permissions_api.get_permissions",
        new_callable=AsyncMock,
    ) as mock_get:
        mock_get.side_effect = AppFileNotFoundError("permissions.json not found")

        response = admin_auth_client.get(
            f"/api/server/{real_bedrock_server.server_name}/permissions/get"
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "not_found"


def test_get_permissions_internal_error(
    admin_auth_client: TestClient, real_bedrock_server
):
    with patch(
        "bedrock_server_manager.web.routers.permissions.permissions_api.get_permissions",
        new_callable=AsyncMock,
    ) as mock_get:
        mock_get.side_effect = BSMError("Failed to parse permissions.json")

        response = admin_auth_client.get(
            f"/api/server/{real_bedrock_server.server_name}/permissions/get"
        )
        assert response.status_code == 500
        assert response.json()["error"]["code"] == "application_error"
