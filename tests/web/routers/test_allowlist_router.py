from unittest.mock import patch

from bedrock_server_manager.error import BSMError, UserInputError
from bedrock_server_manager.web.dependencies import validate_server_exists


@patch("bedrock_server_manager.web.routers.allowlist.allowlist_api.add_to_allowlist")
def test_post_allowlist_user_input_error(mock_add_to_allowlist, authenticated_client):
    authenticated_client.app.dependency_overrides[validate_server_exists] = (
        lambda: "test-server"
    )
    mock_add_to_allowlist.side_effect = UserInputError("Invalid player name")
    response = authenticated_client.post(
        "/api/server/test-server/allowlist/add",
        json={"players": ["invalid name"], "ignoresPlayerLimit": False},
    )
    assert response.status_code == 400
    assert "Invalid player name" in response.json()["detail"]
    authenticated_client.app.dependency_overrides.clear()


@patch("bedrock_server_manager.web.routers.allowlist.allowlist_api.add_to_allowlist")
def test_post_allowlist_bsm_error(mock_add_to_allowlist, authenticated_client):
    authenticated_client.app.dependency_overrides[validate_server_exists] = (
        lambda: "test-server"
    )
    mock_add_to_allowlist.side_effect = BSMError("Failed to add to allowlist")
    response = authenticated_client.post(
        "/api/server/test-server/allowlist/add",
        json={"players": ["player1"], "ignoresPlayerLimit": False},
    )
    assert response.status_code == 500
    assert "Failed to add to allowlist" in response.json()["detail"]
    authenticated_client.app.dependency_overrides.clear()


@patch(
    "bedrock_server_manager.web.routers.allowlist.allowlist_api.remove_from_allowlist"
)
def test_delete_allowlist_route_user_input_error(
    mock_remove_from_allowlist, authenticated_client
):
    authenticated_client.app.dependency_overrides[validate_server_exists] = (
        lambda: "test-server"
    )
    mock_remove_from_allowlist.side_effect = UserInputError("Invalid player name")
    response = authenticated_client.request(
        "DELETE",
        "/api/server/test-server/allowlist/remove",
        json={"players": ["invalid name"]},
    )
    assert response.status_code == 400
    assert "Invalid player name" in response.json()["detail"]
    authenticated_client.app.dependency_overrides.clear()


@patch(
    "bedrock_server_manager.web.routers.allowlist.allowlist_api.remove_from_allowlist"
)
def test_delete_allowlist_route_bsm_error(
    mock_remove_from_allowlist, authenticated_client
):
    authenticated_client.app.dependency_overrides[validate_server_exists] = (
        lambda: "test-server"
    )
    mock_remove_from_allowlist.side_effect = BSMError("Failed to remove from allowlist")
    response = authenticated_client.request(
        "DELETE",
        "/api/server/test-server/allowlist/remove",
        json={"players": ["player1"]},
    )
    assert response.status_code == 500
    assert "Failed to remove from allowlist" in response.json()["detail"]
    authenticated_client.app.dependency_overrides.clear()


def test_get_allowlist(authenticated_client, real_bedrock_server):
    response = authenticated_client.get(
        f"/api/server/{real_bedrock_server.server_name}/allowlist/get"
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_delete_allowlist(authenticated_client, real_bedrock_server):
    response = authenticated_client.request(
        "DELETE",
        f"/api/server/{real_bedrock_server.server_name}/allowlist/remove",
        json={"players": ["player1"]},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_post_allowlist(authenticated_client, real_bedrock_server):
    response = authenticated_client.post(
        f"/api/server/{real_bedrock_server.server_name}/allowlist/add",
        json={"players": ["player1"], "ignoresPlayerLimit": False},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"
