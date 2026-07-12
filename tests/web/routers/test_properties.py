"""
Integration tests for the properties router endpoints.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient

from bedrock_server_manager.error import BSMError, UserInputError


def test_post_properties_set_unauthorized(
    unauth_client: TestClient, real_bedrock_server
):
    response = unauth_client.post(
        f"/api/server/{real_bedrock_server.server_name}/properties/set",
        json={"properties": {"server-name": "My Server"}},
    )
    assert response.status_code == 401


def test_post_properties_set_forbidden(auth_client: TestClient, real_bedrock_server):
    response = auth_client.post(
        f"/api/server/{real_bedrock_server.server_name}/properties/set",
        json={"properties": {"server-name": "My Server"}},
    )
    assert response.status_code == 403


def test_post_properties_set_success(
    admin_auth_client: TestClient, real_bedrock_server
):
    with patch(
        "bedrock_server_manager.web.routers.properties.properties_api.set_properties"
    ) as mock_set:
        mock_set.return_value = {"status": "success", "message": "Properties updated"}

        response = admin_auth_client.post(
            f"/api/server/{real_bedrock_server.server_name}/properties/set",
            json={"properties": {"server-name": "My Server"}},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "success"


def test_post_properties_set_not_found(
    admin_auth_client: TestClient, real_bedrock_server
):
    with patch(
        "bedrock_server_manager.web.routers.properties.properties_api.set_properties"
    ) as mock_set:
        mock_set.return_value = {
            "status": "error",
            "message": "server.properties not found",
        }

        response = admin_auth_client.post(
            f"/api/server/{real_bedrock_server.server_name}/properties/set",
            json={"properties": {"server-name": "My Server"}},
        )
        assert response.status_code == 404
        assert "server.properties not found" in response.json()["detail"]


def test_post_properties_set_error(admin_auth_client: TestClient, real_bedrock_server):
    with patch(
        "bedrock_server_manager.web.routers.properties.properties_api.set_properties"
    ) as mock_set:
        mock_set.return_value = {"status": "error", "message": "Validation failed"}

        response = admin_auth_client.post(
            f"/api/server/{real_bedrock_server.server_name}/properties/set",
            json={"properties": {"server-name": "My Server"}},
        )
        assert response.status_code == 400
        assert "Validation failed" in response.json()["detail"]


def test_post_properties_set_user_input_error(
    admin_auth_client: TestClient, real_bedrock_server
):
    with patch(
        "bedrock_server_manager.web.routers.properties.properties_api.set_properties"
    ) as mock_set:
        mock_set.side_effect = UserInputError("Invalid value for max-players")

        response = admin_auth_client.post(
            f"/api/server/{real_bedrock_server.server_name}/properties/set",
            json={"properties": {"max-players": "-1"}},
        )
        assert response.status_code == 400
        assert "Invalid value for max-players" in response.json()["detail"]


def test_post_properties_set_bsm_error(
    admin_auth_client: TestClient, real_bedrock_server
):
    with patch(
        "bedrock_server_manager.web.routers.properties.properties_api.set_properties"
    ) as mock_set:
        mock_set.side_effect = BSMError("Disk write failed")

        response = admin_auth_client.post(
            f"/api/server/{real_bedrock_server.server_name}/properties/set",
            json={"properties": {"server-name": "My Server"}},
        )
        assert response.status_code == 500
        assert "Disk write failed" in response.json()["detail"]


def test_post_properties_set_exception(
    admin_auth_client: TestClient, real_bedrock_server
):
    with patch(
        "bedrock_server_manager.web.routers.properties.properties_api.set_properties"
    ) as mock_set:
        mock_set.side_effect = Exception("Boom")

        response = admin_auth_client.post(
            f"/api/server/{real_bedrock_server.server_name}/properties/set",
            json={"properties": {"server-name": "My Server"}},
        )
        assert response.status_code == 500
        assert "unexpected error" in response.json()["detail"]


def test_get_properties_unauthorized(unauth_client: TestClient, real_bedrock_server):
    response = unauth_client.get(
        f"/api/server/{real_bedrock_server.server_name}/properties/get"
    )
    assert response.status_code == 401


def test_get_properties_success(admin_auth_client: TestClient, real_bedrock_server):
    with patch(
        "bedrock_server_manager.web.routers.properties.properties_api.get_properties"
    ) as mock_get:
        mock_get.return_value = {
            "status": "success",
            "properties": {"server-name": "Dedicated Server", "gamemode": "survival"},
        }

        response = admin_auth_client.get(
            f"/api/server/{real_bedrock_server.server_name}/properties/get"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["properties"]["gamemode"] == "survival"


def test_get_properties_not_found(admin_auth_client: TestClient, real_bedrock_server):
    with patch(
        "bedrock_server_manager.web.routers.properties.properties_api.get_properties"
    ) as mock_get:
        mock_get.return_value = {
            "status": "error",
            "message": "server.properties not found",
        }

        response = admin_auth_client.get(
            f"/api/server/{real_bedrock_server.server_name}/properties/get"
        )
        assert response.status_code == 404
        assert "server.properties not found" in response.json()["detail"]


def test_get_properties_internal_error(
    admin_auth_client: TestClient, real_bedrock_server
):
    with patch(
        "bedrock_server_manager.web.routers.properties.properties_api.get_properties"
    ) as mock_get:
        mock_get.return_value = {
            "status": "error",
            "message": "Failed to parse properties",
        }

        response = admin_auth_client.get(
            f"/api/server/{real_bedrock_server.server_name}/properties/get"
        )
        assert response.status_code == 500
        assert "Failed to parse properties" in response.json()["detail"]
