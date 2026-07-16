"""
Integration tests for the plugin router endpoints.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient

from bedrock_server_manager.error import BSMError, UserInputError


def test_get_plugin_pages_success(admin_auth_client: TestClient):
    with patch(
        "bedrock_server_manager.plugins.plugin_manager.PluginManager.get_native_ui_routes"
    ) as mock_get:
        mock_get.return_value = [{"name": "TestPage", "url": "/plugin/test"}]

        response = admin_auth_client.get("/api/plugins/pages")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert len(data["pages"]) == 1
        assert data["pages"][0]["name"] == "TestPage"


def test_get_plugin_pages_exception(admin_auth_client: TestClient):
    with patch(
        "bedrock_server_manager.plugins.plugin_manager.PluginManager.get_native_ui_routes"
    ) as mock_get:
        mock_get.side_effect = Exception("System crash")

        # Note: The router catches Exception and returns a JSON response instead of raising HTTPException
        response = admin_auth_client.get("/api/plugins/pages")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        assert "System crash" in data["message"]


def test_get_plugins_status_unauthorized(unauth_client: TestClient):
    response = unauth_client.get("/api/plugins")
    assert response.status_code == 401


def test_get_plugins_status_forbidden(auth_client: TestClient):
    response = auth_client.get("/api/plugins")
    assert response.status_code == 403


def test_get_plugins_status_success(admin_auth_client: TestClient):
    with patch(
        "bedrock_server_manager.web.routers.plugin.plugins_api.get_plugin_statuses"
    ) as mock_get:
        mock_get.return_value = {
            "status": "success",
            "plugins": {
                "TestPlugin": {"name": "TestPlugin", "version": "1.0", "enabled": True}
            },
        }

        response = admin_auth_client.get("/api/plugins")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert len(data["plugins"]) == 1
        assert data["plugins"]["TestPlugin"]["name"] == "TestPlugin"


def test_get_plugins_status_error(admin_auth_client: TestClient):
    with patch(
        "bedrock_server_manager.web.routers.plugin.plugins_api.get_plugin_statuses"
    ) as mock_get:
        mock_get.return_value = {
            "status": "error",
            "message": "Failed to read plugin config",
        }

        response = admin_auth_client.get("/api/plugins")
        assert response.status_code == 500
        assert "Failed to read plugin config" in response.json()["detail"]


def test_post_trigger_event_success(admin_auth_client: TestClient):
    with patch(
        "bedrock_server_manager.web.routers.plugin.plugins_api.trigger_external_plugin_event_api"
    ) as mock_trigger:
        mock_trigger.return_value = {
            "status": "success",
            "message": "Event triggered",
            "details": {},
        }

        response = admin_auth_client.post(
            "/api/plugins/trigger_event",
            json={"event_name": "on_test_event", "payload": {"foo": "bar"}},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["message"] == "Event triggered"


def test_post_trigger_event_error(admin_auth_client: TestClient):
    with patch(
        "bedrock_server_manager.web.routers.plugin.plugins_api.trigger_external_plugin_event_api"
    ) as mock_trigger:
        mock_trigger.return_value = {"status": "error", "message": "Event not found"}

        response = admin_auth_client.post(
            "/api/plugins/trigger_event",
            json={"event_name": "on_test_event", "payload": {}},
        )
        assert response.status_code == 500
        assert "Event not found" in response.json()["detail"]


def test_post_trigger_event_user_input_error(admin_auth_client: TestClient):
    with patch(
        "bedrock_server_manager.web.routers.plugin.plugins_api.trigger_external_plugin_event_api"
    ) as mock_trigger:
        mock_trigger.side_effect = UserInputError("Invalid payload")

        response = admin_auth_client.post(
            "/api/plugins/trigger_event",
            json={"event_name": "on_test_event", "payload": {}},
        )
        assert response.status_code == 400
        assert "Invalid payload" in response.json()["detail"]


def test_post_set_plugin_status_success(admin_auth_client: TestClient):
    with patch(
        "bedrock_server_manager.web.routers.plugin.plugins_api.set_plugin_status"
    ) as mock_set:
        mock_set.return_value = {"status": "success", "message": "Plugin enabled"}

        response = admin_auth_client.post(
            "/api/plugins/MyPlugin", json={"enabled": True}
        )
        assert response.status_code == 200
        assert response.json()["status"] == "success"


def test_post_set_plugin_status_not_found(admin_auth_client: TestClient):
    with patch(
        "bedrock_server_manager.web.routers.plugin.plugins_api.set_plugin_status"
    ) as mock_set:
        mock_set.return_value = {"status": "error", "message": "Plugin not found"}

        response = admin_auth_client.post(
            "/api/plugins/MissingPlugin", json={"enabled": True}
        )
        assert response.status_code == 404
        assert "Plugin not found" in response.json()["detail"]


def test_post_set_plugin_status_bsm_error(admin_auth_client: TestClient):
    with patch(
        "bedrock_server_manager.web.routers.plugin.plugins_api.set_plugin_status"
    ) as mock_set:
        mock_set.side_effect = BSMError("Config write failed")

        response = admin_auth_client.post(
            "/api/plugins/MyPlugin", json={"enabled": False}
        )
        assert response.status_code == 500
        assert "Config write failed" in response.json()["detail"]


def test_put_reload_plugins_success(admin_auth_client: TestClient):
    with patch(
        "bedrock_server_manager.web.routers.plugin.plugins_api.reload_plugins"
    ) as mock_reload:
        mock_reload.return_value = {"status": "success", "message": "Plugins reloaded"}

        response = admin_auth_client.put("/api/plugins/reload")
        assert response.status_code == 200
        assert response.json()["status"] == "success"


def test_put_reload_plugins_error(admin_auth_client: TestClient):
    with patch(
        "bedrock_server_manager.web.routers.plugin.plugins_api.reload_plugins"
    ) as mock_reload:
        mock_reload.return_value = {
            "status": "error",
            "message": "Failed to initialize plugins",
        }

        response = admin_auth_client.put("/api/plugins/reload")
        assert response.status_code == 500
        assert "Failed to initialize plugins" in response.json()["detail"]
