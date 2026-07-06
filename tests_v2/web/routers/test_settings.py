"""
Integration tests for the settings router endpoints.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient

from bedrock_server_manager.error import BSMError, UserInputError


def test_get_all_settings_unauthorized(unauth_client: TestClient):
    response = unauth_client.get("/api/settings/get")
    assert response.status_code == 401


def test_get_all_settings_forbidden(auth_client: TestClient):
    response = auth_client.get("/api/settings/get")
    assert response.status_code == 403


def test_get_all_settings_success(admin_auth_client: TestClient):
    with patch(
        "bedrock_server_manager.web.routers.settings.settings_api.get_all_global_settings"
    ) as mock_get:
        mock_get.return_value = {
            "status": "success",
            "message": "Settings retrieved",
            "app.theme": "dark",
            "web.port": 8080,
        }

        response = admin_auth_client.get("/api/settings/get")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["settings"]["app.theme"] == "dark"


def test_get_all_settings_error(admin_auth_client: TestClient):
    with patch(
        "bedrock_server_manager.web.routers.settings.settings_api.get_all_global_settings"
    ) as mock_get:
        mock_get.return_value = {
            "status": "error",
            "message": "Failed to read config file",
        }

        response = admin_auth_client.get("/api/settings/get")
        assert response.status_code == 500
        assert "Failed to read config file" in response.json()["detail"]


def test_get_all_settings_exception(admin_auth_client: TestClient):
    with patch(
        "bedrock_server_manager.web.routers.settings.settings_api.get_all_global_settings"
    ) as mock_get:
        mock_get.side_effect = Exception("Crash")

        response = admin_auth_client.get("/api/settings/get")
        assert response.status_code == 500
        assert "unexpected error" in response.json()["detail"].lower()


def test_post_set_setting_success(admin_auth_client: TestClient):
    with patch(
        "bedrock_server_manager.web.routers.settings.settings_api.set_global_setting"
    ) as mock_set:
        mock_set.return_value = {"status": "success", "message": "Setting updated"}

        response = admin_auth_client.post(
            "/api/settings/set", json={"key": "app.theme", "value": "light"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["setting"]["key"] == "app.theme"


def test_post_set_setting_error(admin_auth_client: TestClient):
    with patch(
        "bedrock_server_manager.web.routers.settings.settings_api.set_global_setting"
    ) as mock_set:
        mock_set.return_value = {"status": "error", "message": "Invalid key"}

        response = admin_auth_client.post(
            "/api/settings/set", json={"key": "invalid.key", "value": "light"}
        )
        assert response.status_code == 400
        assert "Invalid key" in response.json()["detail"]


def test_post_set_setting_user_input_error(admin_auth_client: TestClient):
    with patch(
        "bedrock_server_manager.web.routers.settings.settings_api.set_global_setting"
    ) as mock_set:
        mock_set.side_effect = UserInputError("Value must be string")

        response = admin_auth_client.post(
            "/api/settings/set", json={"key": "app.theme", "value": 123}
        )
        assert response.status_code == 400
        assert "Value must be string" in response.json()["detail"]


def test_post_set_setting_bsm_error(admin_auth_client: TestClient):
    with patch(
        "bedrock_server_manager.web.routers.settings.settings_api.set_global_setting"
    ) as mock_set:
        mock_set.side_effect = BSMError("Disk write failed")

        response = admin_auth_client.post(
            "/api/settings/set", json={"key": "app.theme", "value": "light"}
        )
        assert response.status_code == 500
        assert "Disk write failed" in response.json()["detail"]


def test_put_reload_settings_success(admin_auth_client: TestClient):
    with patch(
        "bedrock_server_manager.web.routers.settings.settings_api.reload_global_settings"
    ) as mock_reload:
        mock_reload.return_value = {"status": "success", "message": "Reloaded"}

        response = admin_auth_client.put("/api/settings/reload")
        assert response.status_code == 200
        assert response.json()["status"] == "success"


def test_put_reload_settings_error(admin_auth_client: TestClient):
    with patch(
        "bedrock_server_manager.web.routers.settings.settings_api.reload_global_settings"
    ) as mock_reload:
        mock_reload.return_value = {"status": "error", "message": "Failed to reload"}

        response = admin_auth_client.put("/api/settings/reload")
        assert response.status_code == 500
        assert "Failed to reload" in response.json()["detail"]
