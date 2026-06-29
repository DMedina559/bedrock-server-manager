from unittest.mock import patch

from bedrock_server_manager.web.deps import validate_server_exists


@patch("bedrock_server_manager.web.routers.properties.properties_api.set_properties")
def test_post_properties_user_input_error(mock_modify_properties, authenticated_client):
    """Test the configure_properties_api_route with a UserInputError."""
    from bedrock_server_manager.error import UserInputError

    authenticated_client.app.dependency_overrides[validate_server_exists] = (
        lambda: "test-server"
    )
    mock_modify_properties.side_effect = UserInputError("Invalid property")
    response = authenticated_client.post(
        "/api/server/test-server/properties/set",
        json={"properties": {"invalid-property": "test"}},
    )
    assert response.status_code == 400
    assert "Invalid property" in response.json()["detail"]
    authenticated_client.app.dependency_overrides.clear()


@patch("bedrock_server_manager.web.routers.properties.properties_api.set_properties")
def test_post_properties_bsm_error(mock_modify_properties, authenticated_client):
    """Test the configure_properties_api_route with a BSMError."""
    from bedrock_server_manager.error import BSMError

    authenticated_client.app.dependency_overrides[validate_server_exists] = (
        lambda: "test-server"
    )
    mock_modify_properties.side_effect = BSMError("Failed to modify properties")
    response = authenticated_client.post(
        "/api/server/test-server/properties/set",
        json={"properties": {"level-name": "test"}},
    )
    assert response.status_code == 500
    assert "Failed to modify properties" in response.json()["detail"]
    authenticated_client.app.dependency_overrides.clear()


def test_get_properties(authenticated_client, real_bedrock_server):
    response = authenticated_client.get(
        f"/api/server/{real_bedrock_server.server_name}/properties/get"
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_post_properties(authenticated_client, real_bedrock_server):
    """Test the configure_properties_api_route with a successful response."""
    response = authenticated_client.post(
        f"/api/server/{real_bedrock_server.server_name}/properties/set",
        json={"properties": {"level-name": "test"}},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"
