from unittest.mock import patch

from bedrock_server_manager.web.dependencies import validate_server_exists


@patch("bedrock_server_manager.web.routers.permissions.permissions_api.set_permissions")
def test_put_permissions_user_input_error(
    mock_configure_permission, authenticated_client
):
    """Test the configure_permissions_api_route with a UserInputError."""
    from bedrock_server_manager.error import UserInputError

    authenticated_client.app.dependency_overrides[validate_server_exists] = (
        lambda: "test-server"
    )
    mock_configure_permission.side_effect = UserInputError("Invalid permission level")
    response = authenticated_client.post(
        "/api/server/test-server/permissions/set",
        json={
            "permissions": [
                {
                    "xuid": "123",
                    "name": "player1",
                    "permission_level": "invalid",
                }
            ]
        },
    )
    assert response.status_code == 400
    assert "Invalid permission level" in response.json()["errors"]["123"]
    authenticated_client.app.dependency_overrides.clear()


@patch("bedrock_server_manager.web.routers.permissions.permissions_api.set_permissions")
def test_put_permissions_bsm_error(mock_configure_permission, authenticated_client):
    """Test the configure_permissions_api_route with a BSMError."""
    from bedrock_server_manager.error import BSMError

    authenticated_client.app.dependency_overrides[validate_server_exists] = (
        lambda: "test-server"
    )
    mock_configure_permission.side_effect = BSMError("Failed to configure permission")
    response = authenticated_client.post(
        "/api/server/test-server/permissions/set",
        json={
            "permissions": [
                {
                    "xuid": "123",
                    "name": "player1",
                    "permission_level": "operator",
                }
            ]
        },
    )
    assert response.status_code == 400
    assert "Failed to configure permission" in response.json()["errors"]["123"]
    authenticated_client.app.dependency_overrides.clear()


def test_get_permissions(authenticated_client, real_bedrock_server):
    """Test the get_server_permissions_api_route with a successful response."""
    response = authenticated_client.get(
        f"/api/server/{real_bedrock_server.server_name}/permissions/get"
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_put_permissions(authenticated_client, real_bedrock_server):
    """Test the configure_permissions_api_route with a successful response."""
    response = authenticated_client.post(
        f"/api/server/{real_bedrock_server.server_name}/permissions/set",
        json={
            "permissions": [
                {
                    "xuid": "123",
                    "name": "player1",
                    "permission_level": "operator",
                }
            ]
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"
