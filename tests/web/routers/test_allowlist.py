"""
Integration tests for the allowlist router endpoints.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient

from bedrock_server_manager.error import BSMError, UserInputError


def test_post_allowlist_success(admin_auth_client: TestClient, real_bedrock_server):
    """Test adding players to the allowlist successfully."""
    with patch("bedrock_server_manager.api.allowlist.add_to_allowlist") as mock_add:
        mock_add.return_value = {"status": "success", "message": "Players added"}

        response = admin_auth_client.post(
            f"/api/server/{real_bedrock_server.server_name}/allowlist/add",
            json={"players": ["Steve", "Alex"], "ignoresPlayerLimit": False},
        )

        assert response.status_code == 200
        assert response.json()["status"] == "success"
        assert response.json()["message"] == "Players added"

        mock_add.assert_called_once()
        call_args = mock_add.call_args[1]
        assert call_args["server_name"] == real_bedrock_server.server_name
        assert call_args["new_players_data"] == [
            {"name": "Steve", "ignoresPlayerLimit": False},
            {"name": "Alex", "ignoresPlayerLimit": False},
        ]


def test_post_allowlist_unauthorized(unauth_client: TestClient, real_bedrock_server):
    """Test adding to allowlist without authentication."""
    response = unauth_client.post(
        f"/api/server/{real_bedrock_server.server_name}/allowlist/add",
        json={"players": ["Steve"], "ignoresPlayerLimit": False},
    )
    assert response.status_code == 401


def test_post_allowlist_user_input_error(
    admin_auth_client: TestClient, real_bedrock_server
):
    """Test adding to allowlist when API raises UserInputError."""
    with patch("bedrock_server_manager.api.allowlist.add_to_allowlist") as mock_add:
        mock_add.side_effect = UserInputError("Invalid player name")

        response = admin_auth_client.post(
            f"/api/server/{real_bedrock_server.server_name}/allowlist/add",
            json={"players": ["@Invalid"], "ignoresPlayerLimit": False},
        )

        assert response.status_code == 400
        assert "Invalid player name" in response.json()["detail"]


def test_get_allowlist_success(admin_auth_client: TestClient, real_bedrock_server):
    """Test retrieving the allowlist successfully."""
    with patch("bedrock_server_manager.api.allowlist.get_allowlist") as mock_get:
        mock_get.return_value = {
            "status": "success",
            "players": [
                {"name": "Steve", "ignoresPlayerLimit": False},
                {"name": "Alex", "ignoresPlayerLimit": True},
            ],
        }

        response = admin_auth_client.get(
            f"/api/server/{real_bedrock_server.server_name}/allowlist/get"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert len(data["players"]) == 2
        assert data["players"][0]["name"] == "Steve"


def test_get_allowlist_not_found(admin_auth_client: TestClient, real_bedrock_server):
    """Test retrieving allowlist when file is not found."""
    with patch("bedrock_server_manager.api.allowlist.get_allowlist") as mock_get:
        mock_get.return_value = {
            "status": "error",
            "message": "allowlist.json not found",
        }

        response = admin_auth_client.get(
            f"/api/server/{real_bedrock_server.server_name}/allowlist/get"
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


def test_get_allowlist_error(admin_auth_client: TestClient, real_bedrock_server):
    """Test retrieving allowlist generic error."""
    with patch("bedrock_server_manager.api.allowlist.get_allowlist") as mock_get:
        mock_get.return_value = {"status": "error", "message": "Failed to parse JSON"}

        response = admin_auth_client.get(
            f"/api/server/{real_bedrock_server.server_name}/allowlist/get"
        )

        assert response.status_code == 500
        assert "Failed to parse JSON" in response.json()["detail"]


def test_delete_allowlist_success(admin_auth_client: TestClient, real_bedrock_server):
    """Test removing players from the allowlist successfully."""
    with patch(
        "bedrock_server_manager.api.allowlist.remove_from_allowlist"
    ) as mock_remove:
        mock_remove.return_value = {"status": "success", "message": "Players removed"}

        response = admin_auth_client.request(
            "DELETE",
            f"/api/server/{real_bedrock_server.server_name}/allowlist/remove",
            json={"players": ["Steve"]},
        )

        assert response.status_code == 200
        assert response.json()["status"] == "success"

        mock_remove.assert_called_once()
        call_args = mock_remove.call_args[1]
        assert call_args["server_name"] == real_bedrock_server.server_name
        assert call_args["player_names"] == ["Steve"]


def test_delete_allowlist_bsm_error(admin_auth_client: TestClient, real_bedrock_server):
    """Test removing from allowlist when API raises BSMError."""
    with patch(
        "bedrock_server_manager.api.allowlist.remove_from_allowlist"
    ) as mock_remove:
        mock_remove.side_effect = BSMError("Internal system failure")

        response = admin_auth_client.request(
            "DELETE",
            f"/api/server/{real_bedrock_server.server_name}/allowlist/remove",
            json={"players": ["Steve"]},
        )

        assert response.status_code == 500
        assert "Internal system failure" in response.json()["detail"]
