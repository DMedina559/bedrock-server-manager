"""
Integration tests for the bans router endpoints.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient


def test_get_server_bans_unauthorized(
    unauth_client: TestClient, real_bedrock_server, test_user
):
    """Test getting server bans without authentication."""
    response = unauth_client.get(
        f"/api/server/{real_bedrock_server.server_name}/bans/get"
    )
    assert response.status_code == 401


def test_get_server_bans_forbidden(auth_client: TestClient, real_bedrock_server):
    """Test getting server bans with standard user permissions."""
    response = auth_client.get(
        f"/api/server/{real_bedrock_server.server_name}/bans/get"
    )
    assert response.status_code == 403


def test_get_server_bans_success(admin_auth_client: TestClient, real_bedrock_server):
    """Test getting server bans successfully with admin permissions."""
    with patch(
        "bedrock_server_manager.web.routers.bans.get_server_bans_api"
    ) as mock_api:
        mock_api.return_value = {
            "status": "success",
            "message": "Bans retrieved",
            "bans": [{"xuid": "123", "name": "BannedPlayer", "reason": "Testing"}],
        }
        response = admin_auth_client.get(
            f"/api/server/{real_bedrock_server.server_name}/bans/get"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert len(data["bans"]) == 1
        assert data["bans"][0]["name"] == "BannedPlayer"


def test_get_server_bans_error(admin_auth_client: TestClient, real_bedrock_server):
    """Test getting server bans when API returns error."""
    with patch(
        "bedrock_server_manager.web.routers.bans.get_server_bans_api"
    ) as mock_api:
        mock_api.return_value = {
            "status": "error",
            "message": "Failed to read allowlist.json",
        }
        response = admin_auth_client.get(
            f"/api/server/{real_bedrock_server.server_name}/bans/get"
        )
        assert response.status_code == 400
        assert "Failed to read allowlist.json" in response.json()["detail"]


def test_post_add_server_ban_success(
    admin_auth_client: TestClient, real_bedrock_server
):
    """Test adding a server ban successfully."""
    with patch(
        "bedrock_server_manager.web.routers.bans.add_server_ban_api"
    ) as mock_api:
        mock_api.return_value = {"status": "success", "message": "Player banned"}
        response = admin_auth_client.post(
            f"/api/server/{real_bedrock_server.server_name}/bans/add",
            json={"player_name": "BadPlayer", "xuid": "12345", "reason": "Hacking"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "success"


def test_post_add_server_ban_error(admin_auth_client: TestClient, real_bedrock_server):
    """Test adding a server ban when API returns error."""
    with patch(
        "bedrock_server_manager.web.routers.bans.add_server_ban_api"
    ) as mock_api:
        mock_api.return_value = {"status": "error", "message": "Player not found"}
        response = admin_auth_client.post(
            f"/api/server/{real_bedrock_server.server_name}/bans/add",
            json={"player_name": "BadPlayer", "xuid": "12345", "reason": "Hacking"},
        )
        assert response.status_code == 400
        assert "Player not found" in response.json()["detail"]


def test_delete_remove_server_ban_success(
    admin_auth_client: TestClient, real_bedrock_server
):
    """Test removing a server ban successfully."""
    with patch(
        "bedrock_server_manager.web.routers.bans.remove_server_ban_api"
    ) as mock_api:
        mock_api.return_value = {"status": "success", "message": "Player unbanned"}

        # httpx testclient needs request for delete with body

        response = admin_auth_client.request(
            "DELETE",
            f"/api/server/{real_bedrock_server.server_name}/bans/remove",
            json={"xuid": "12345"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "success"


def test_delete_remove_server_ban_error(
    admin_auth_client: TestClient, real_bedrock_server
):
    """Test removing a server ban when API returns error."""
    with patch(
        "bedrock_server_manager.web.routers.bans.remove_server_ban_api"
    ) as mock_api:
        mock_api.return_value = {"status": "error", "message": "Ban not found"}

        response = admin_auth_client.request(
            "DELETE",
            f"/api/server/{real_bedrock_server.server_name}/bans/remove",
            json={"xuid": "12345"},
        )
        assert response.status_code == 400
        assert "Ban not found" in response.json()["detail"]
