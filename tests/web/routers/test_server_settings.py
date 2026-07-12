from unittest.mock import patch

from fastapi.testclient import TestClient

from bedrock_server_manager.error import BSMError, InvalidServerNameError


def test_get_server_settings_unauthorized(
    unauth_client: TestClient, real_bedrock_server
):
    response = unauth_client.get(
        f"/api/server/{real_bedrock_server.server_name}/settings/get"
    )
    assert response.status_code == 401


def test_get_server_settings_success(
    admin_auth_client: TestClient, real_bedrock_server
):
    with patch(
        "bedrock_server_manager.core.bedrock_server.BedrockServer._load_server_config"
    ) as mock_load:
        mock_load.return_value = {"settings": {"autoupdate": True}}

        response = admin_auth_client.get(
            f"/api/server/{real_bedrock_server.server_name}/settings/get"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["settings"]["settings"]["autoupdate"] is True


def test_get_server_settings_not_found(
    admin_auth_client: TestClient, real_bedrock_server
):
    with patch(
        "bedrock_server_manager.utils.server.validate_server", return_value=True
    ):
        with patch("bedrock_server_manager.context.AppContext.get_server") as mock_get:
            mock_get.side_effect = InvalidServerNameError(
                real_bedrock_server.server_name
            )

            response = admin_auth_client.get(
                f"/api/server/{real_bedrock_server.server_name}/settings/get"
            )
            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()


def test_get_server_settings_exception(
    admin_auth_client: TestClient, real_bedrock_server
):
    with patch(
        "bedrock_server_manager.utils.server.validate_server", return_value=True
    ):
        with patch("bedrock_server_manager.context.AppContext.get_server") as mock_get:
            mock_get.side_effect = Exception("System Crash")

            response = admin_auth_client.get(
                f"/api/server/{real_bedrock_server.server_name}/settings/get"
            )
            assert response.status_code == 500
            assert "unexpected error" in response.json()["detail"].lower()


def test_post_set_server_setting_unauthorized(
    unauth_client: TestClient, real_bedrock_server
):
    response = unauth_client.post(
        f"/api/server/{real_bedrock_server.server_name}/settings/set",
        json={"key": "settings.autoupdate", "value": False},
    )
    assert response.status_code == 401


def test_post_set_server_setting_forbidden(
    auth_client: TestClient, real_bedrock_server
):
    response = auth_client.post(
        f"/api/server/{real_bedrock_server.server_name}/settings/set",
        json={"key": "settings.autoupdate", "value": False},
    )
    assert response.status_code == 403


def test_post_set_server_setting_success(
    admin_auth_client: TestClient, real_bedrock_server
):
    with patch(
        "bedrock_server_manager.core.bedrock_server.BedrockServer._manage_json_config"
    ) as mock_manage:
        response = admin_auth_client.post(
            f"/api/server/{real_bedrock_server.server_name}/settings/set",
            json={"key": "settings.autoupdate", "value": False},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["setting"]["key"] == "settings.autoupdate"
        mock_manage.assert_called_once_with(
            key="settings.autoupdate", operation="write", value=False
        )


def test_post_set_server_setting_not_found(
    admin_auth_client: TestClient, real_bedrock_server
):
    with patch(
        "bedrock_server_manager.utils.server.validate_server", return_value=True
    ):
        with patch("bedrock_server_manager.context.AppContext.get_server") as mock_get:
            mock_get.side_effect = InvalidServerNameError(
                real_bedrock_server.server_name
            )

            response = admin_auth_client.post(
                f"/api/server/{real_bedrock_server.server_name}/settings/set",
                json={"key": "settings.autoupdate", "value": False},
            )
            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()


def test_post_set_server_setting_bsm_error(
    admin_auth_client: TestClient, real_bedrock_server
):
    with patch(
        "bedrock_server_manager.utils.server.validate_server", return_value=True
    ):
        with patch("bedrock_server_manager.context.AppContext.get_server") as mock_get:
            mock_get.side_effect = BSMError("Corrupted config")

            response = admin_auth_client.post(
                f"/api/server/{real_bedrock_server.server_name}/settings/set",
                json={"key": "settings.autoupdate", "value": False},
            )
            assert response.status_code == 500
            assert "Corrupted config" in response.json()["detail"]
