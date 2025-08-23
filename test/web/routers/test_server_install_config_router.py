from unittest.mock import patch, MagicMock

import pytest
from bedrock_server_manager.web.dependencies import validate_server_exists


import os


def test_get_custom_zips(authenticated_client, app_context):
    """Test the get_custom_zips route with a successful response."""
    custom_dir = os.path.join(app_context.settings.get("paths.downloads"), "custom")
    os.makedirs(custom_dir, exist_ok=True)
    zip_file = os.path.join(custom_dir, "zip1.zip")
    with open(zip_file, "w") as f:
        f.write("test")

    response = authenticated_client.get("/api/downloads/list")
    assert response.status_code == 200
    assert "zip1.zip" in response.json()["custom_zips"]


def test_install_server_api_route_success(authenticated_client):
    """Test the install_server_api_route with a successful installation."""
    app_context = authenticated_client.app.state.app_context
    app_context.task_manager.run_task = MagicMock(return_value="install-task-id")

    # Mock the utils functions that are called before the task is created
    with patch(
        "bedrock_server_manager.web.routers.server_install_config.utils_api.validate_server_name_format",
        return_value={"status": "success"},
    ):
        with patch(
            "bedrock_server_manager.web.routers.server_install_config.utils_api.validate_server_exist",
            return_value={"status": "error"},
        ):
            response = authenticated_client.post(
                "/api/server/install",
                json={"server_name": "new-server", "server_version": "LATEST"},
            )

    assert response.status_code == 200
    json_data = response.json()
    assert json_data["status"] == "pending"
    assert json_data["task_id"] == "install-task-id"
    app_context.task_manager.run_task.assert_called_once()


@patch(
    "bedrock_server_manager.web.routers.server_install_config.server_install_config.modify_server_properties"
)
def test_configure_properties_api_route_user_input_error(
    mock_modify_properties, authenticated_client
):
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


@patch(
    "bedrock_server_manager.web.routers.server_install_config.server_install_config.modify_server_properties"
)
def test_configure_properties_api_route_bsm_error(
    mock_modify_properties, authenticated_client
):
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


@patch(
    "bedrock_server_manager.web.routers.server_install_config.server_install_config.add_players_to_allowlist_api"
)
def test_add_to_allowlist_api_route_user_input_error(
    mock_add_to_allowlist, authenticated_client
):
    """Test the add_to_allowlist_api_route with a UserInputError."""
    from bedrock_server_manager.error import UserInputError

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


@patch(
    "bedrock_server_manager.web.routers.server_install_config.server_install_config.add_players_to_allowlist_api"
)
def test_add_to_allowlist_api_route_bsm_error(
    mock_add_to_allowlist, authenticated_client
):
    """Test the add_to_allowlist_api_route with a BSMError."""
    from bedrock_server_manager.error import BSMError

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
    "bedrock_server_manager.web.routers.server_install_config.server_install_config.remove_players_from_allowlist"
)
def test_remove_from_allowlist_api_route_user_input_error(
    mock_remove_from_allowlist, authenticated_client
):
    """Test the remove_from_allowlist_api_route with a UserInputError."""
    from bedrock_server_manager.error import UserInputError

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
    "bedrock_server_manager.web.routers.server_install_config.server_install_config.remove_players_from_allowlist"
)
def test_remove_from_allowlist_api_route_bsm_error(
    mock_remove_from_allowlist, authenticated_client
):
    """Test the remove_from_allowlist_api_route with a BSMError."""
    from bedrock_server_manager.error import BSMError

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


@patch(
    "bedrock_server_manager.web.routers.server_install_config.server_install_config.configure_player_permission"
)
def test_configure_permissions_api_route_user_input_error(
    mock_configure_permission, authenticated_client
):
    """Test the configure_permissions_api_route with a UserInputError."""
    from bedrock_server_manager.error import UserInputError

    authenticated_client.app.dependency_overrides[validate_server_exists] = (
        lambda: "test-server"
    )
    mock_configure_permission.side_effect = UserInputError("Invalid permission level")
    response = authenticated_client.put(
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


@patch(
    "bedrock_server_manager.web.routers.server_install_config.server_install_config.configure_player_permission"
)
def test_configure_permissions_api_route_bsm_error(
    mock_configure_permission, authenticated_client
):
    """Test the configure_permissions_api_route with a BSMError."""
    from bedrock_server_manager.error import BSMError

    authenticated_client.app.dependency_overrides[validate_server_exists] = (
        lambda: "test-server"
    )
    mock_configure_permission.side_effect = BSMError("Failed to configure permission")
    response = authenticated_client.put(
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


@patch(
    "bedrock_server_manager.web.routers.server_install_config.system_api.set_autoupdate"
)
def test_configure_service_api_route_user_input_error(
    mock_set_autoupdate, authenticated_client
):
    """Test the configure_service_api_route with a UserInputError."""
    from bedrock_server_manager.error import UserInputError

    authenticated_client.app.dependency_overrides[validate_server_exists] = (
        lambda: "test-server"
    )
    mock_set_autoupdate.side_effect = UserInputError("Invalid value")
    response = authenticated_client.post(
        "/api/server/test-server/service/update",
        json={"autoupdate": "invalid"},
    )
    assert response.status_code == 422
    authenticated_client.app.dependency_overrides.clear()


@patch(
    "bedrock_server_manager.web.routers.server_install_config.system_api.set_autoupdate"
)
def test_configure_service_api_route_bsm_error(
    mock_set_autoupdate, authenticated_client
):
    """Test the configure_service_api_route with a BSMError."""
    from bedrock_server_manager.error import BSMError

    authenticated_client.app.dependency_overrides[validate_server_exists] = (
        lambda: "test-server"
    )
    mock_set_autoupdate.side_effect = BSMError("Failed to set autoupdate")
    response = authenticated_client.post(
        "/api/server/test-server/service/update",
        json={"autoupdate": True},
    )
    assert response.status_code == 500
    assert "Failed to set autoupdate" in response.json()["detail"]
    authenticated_client.app.dependency_overrides.clear()


def test_get_server_permissions_api_route(authenticated_client, real_bedrock_server):
    """Test the get_server_permissions_api_route with a successful response."""
    response = authenticated_client.get(
        f"/api/server/{real_bedrock_server.server_name}/permissions/get"
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"


@patch(
    "bedrock_server_manager.web.routers.server_install_config.system_api.set_autoupdate",
    return_value={"status": "success"},
)
def test_configure_service_api_route(
    mock_set_autoupdate, authenticated_client, real_bedrock_server
):
    """Test the configure_service_api_route with a successful response."""
    response = authenticated_client.post(
        f"/api/server/{real_bedrock_server.server_name}/service/update",
        json={"autoupdate": True},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_configure_permissions_api_route(authenticated_client, real_bedrock_server):
    """Test the configure_permissions_api_route with a successful response."""
    response = authenticated_client.put(
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


def test_get_allowlist_api_route(authenticated_client, real_bedrock_server):
    """Test the get_allowlist_api_route with a successful response."""
    response = authenticated_client.get(
        f"/api/server/{real_bedrock_server.server_name}/allowlist/get"
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_remove_allowlist_players_api_route(authenticated_client, real_bedrock_server):
    """Test the remove_allowlist_players_api_route with a successful response."""
    response = authenticated_client.request(
        "DELETE",
        f"/api/server/{real_bedrock_server.server_name}/allowlist/remove",
        json={"players": ["player1"]},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_get_server_properties_api_route(authenticated_client, real_bedrock_server):
    """Test the get_server_properties_api_route with a successful response."""
    response = authenticated_client.get(
        f"/api/server/{real_bedrock_server.server_name}/properties/get"
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_add_to_allowlist_api_route(authenticated_client, real_bedrock_server):
    """Test the add_to_allowlist_api_route with a successful response."""
    response = authenticated_client.post(
        f"/api/server/{real_bedrock_server.server_name}/allowlist/add",
        json={"players": ["player1"], "ignoresPlayerLimit": False},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"


@patch(
    "bedrock_server_manager.web.routers.server_install_config.utils_api.validate_server_exist"
)
@patch(
    "bedrock_server_manager.web.routers.server_install_config.utils_api.validate_server_name_format"
)
def test_install_server_api_route_confirmation_needed(
    mock_validate_name, mock_validate_exist, authenticated_client
):
    """Test the install_server_api_route when confirmation is needed."""
    mock_validate_name.return_value = {"status": "success"}
    mock_validate_exist.return_value = {"status": "success"}

    response = authenticated_client.post(
        "/api/server/install",
        json={"server_name": "existing-server", "server_version": "LATEST"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "confirm_needed"


@patch(
    "bedrock_server_manager.web.routers.server_install_config.utils_api.validate_server_name_format"
)
def test_install_server_api_route_invalid_name(
    mock_validate_name, authenticated_client
):
    """Test the install_server_api_route with an invalid server name."""
    mock_validate_name.return_value = {
        "status": "error",
        "message": "Invalid server name",
    }

    response = authenticated_client.post(
        "/api/server/install",
        json={"server_name": "invalid name", "server_version": "LATEST"},
    )
    assert response.status_code == 400
    assert "Invalid server name" in response.json()["detail"]


def test_configure_properties_page(authenticated_client, real_bedrock_server):
    """Test the configure_properties_page route with a successful response."""
    response = authenticated_client.get(
        f"/server/{real_bedrock_server.server_name}/configure_properties"
    )
    assert response.status_code == 200
    assert "Server Properties" in response.text


def test_configure_allowlist_page(authenticated_client, real_bedrock_server):
    """Test the configure_allowlist_page route with a successful response."""
    response = authenticated_client.get(
        f"/server/{real_bedrock_server.server_name}/configure_allowlist"
    )
    assert response.status_code == 200
    assert "Allowlist" in response.text


def test_configure_permissions_page(authenticated_client, real_bedrock_server):
    """Test the configure_permissions_page route with a successful response."""
    response = authenticated_client.get(
        f"/server/{real_bedrock_server.server_name}/configure_permissions"
    )
    assert response.status_code == 200
    assert "Permissions" in response.text


def test_configure_service_page(authenticated_client, real_bedrock_server):
    """Test the configure_service_page route with a successful response."""
    response = authenticated_client.get(
        f"/server/{real_bedrock_server.server_name}/configure_service"
    )
    assert response.status_code == 200
    assert "Service" in response.text


def test_configure_properties_api_route(authenticated_client, real_bedrock_server):
    """Test the configure_properties_api_route with a successful response."""
    response = authenticated_client.post(
        f"/api/server/{real_bedrock_server.server_name}/properties/set",
        json={"properties": {"level-name": "test"}},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"
