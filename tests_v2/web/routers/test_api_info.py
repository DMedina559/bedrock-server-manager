"""
Integration tests for the api_info router endpoints.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient

from bedrock_server_manager.error import BSMError


def test_get_server_running_status_success(
    auth_client: TestClient, real_bedrock_server
):
    with patch(
        "bedrock_server_manager.api.system.get_server_running_status"
    ) as mock_status:
        mock_status.return_value = {
            "status": "success",
            "is_running": True,
            "message": "Server is running.",
        }

        response = auth_client.get(
            f"/api/server/{real_bedrock_server.server_name}/status"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["running"] is True


def test_get_server_running_status_error(auth_client: TestClient, real_bedrock_server):
    with patch(
        "bedrock_server_manager.api.system.get_server_running_status"
    ) as mock_status:
        mock_status.side_effect = BSMError("Unable to fetch status")

        response = auth_client.get(
            f"/api/server/{real_bedrock_server.server_name}/status"
        )

        assert response.status_code == 500
        assert "Unable to fetch status" in response.json()["detail"]


def test_get_validate_server_success(auth_client: TestClient, real_bedrock_server):
    with patch("bedrock_server_manager.utils.server.validate_server") as mock_validate:
        mock_validate.return_value = True

        response = auth_client.get(
            f"/api/server/{real_bedrock_server.server_name}/validate"
        )

        assert response.status_code == 200
        assert response.json()["status"] == "success"


def test_get_validate_server_not_found(auth_client: TestClient, real_bedrock_server):
    with patch("bedrock_server_manager.utils.server.validate_server") as mock_validate:
        mock_validate.return_value = False

        response = auth_client.get(
            f"/api/server/{real_bedrock_server.server_name}/validate"
        )

        assert response.status_code == 404


def test_get_server_process_info_success(auth_client: TestClient, real_bedrock_server):
    with patch(
        "bedrock_server_manager.api.system.get_bedrock_process_info"
    ) as mock_info:
        mock_info.return_value = {
            "status": "success",
            "process_info": {"cpu": 10.5, "mem": 1024, "threads": 5},
        }

        response = auth_client.get(
            f"/api/server/{real_bedrock_server.server_name}/process_info"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["process_info"]["cpu"] == 10.5


def test_put_scan_players_success(admin_auth_client: TestClient):
    with patch(
        "bedrock_server_manager.api.player.scan_and_update_player_db_api"
    ) as mock_scan:
        mock_scan.return_value = {
            "status": "success",
            "message": "Scanned 1 player",
            "details": {"test_server": 1},
        }

        response = admin_auth_client.put("/api/players/scan")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["details"] == {"test_server": 1}


def test_get_all_players_success(admin_auth_client: TestClient):
    with patch(
        "bedrock_server_manager.api.player.get_all_known_players_api"
    ) as mock_get:
        mock_get.return_value = {
            "status": "success",
            "players": [{"xuid": "123", "name": "Steve"}],
            "message": "Success",
        }

        response = admin_auth_client.get("/api/players/get")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert len(data["players"]) == 1


def test_put_prune_downloads_success(
    admin_auth_client: TestClient, tmp_path, app_context
):
    downloads_dir = tmp_path / "downloads"
    downloads_dir.mkdir()
    target_dir = downloads_dir / "test_target"
    target_dir.mkdir()
    app_context.settings.set("paths.downloads", str(downloads_dir))

    with patch("bedrock_server_manager.api.misc.prune_download_cache") as mock_prune:
        mock_prune.return_value = {
            "status": "success",
            "files_deleted": 2,
            "files_kept": 1,
        }

        response = admin_auth_client.put(
            "/api/downloads/prune", json={"directory": "test_target", "keep": 1}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["files_deleted"] == 2


def test_put_prune_downloads_invalid_path(
    admin_auth_client: TestClient, tmp_path, app_context
):
    downloads_dir = tmp_path / "downloads"
    downloads_dir.mkdir()
    app_context.settings.set("paths.downloads", str(downloads_dir))

    response = admin_auth_client.put(
        "/api/downloads/prune", json={"directory": "../../etc/passwd", "keep": 1}
    )

    assert response.status_code == 400


def test_get_servers_list_success(auth_client: TestClient):
    with patch(
        "bedrock_server_manager.api.application.get_all_servers_data"
    ) as mock_list:
        mock_list.return_value = {
            "status": "success",
            "servers": [
                {
                    "name": "test_server",
                    "status": "running",
                    "version": "1.20.0",
                    "player_count": 0,
                }
            ],
        }

        response = auth_client.get("/api/servers")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert len(data["servers"]) == 1


def test_get_system_info_success(unauth_client: TestClient):
    with patch(
        "bedrock_server_manager.api.application.get_system_and_app_info"
    ) as mock_info:
        mock_info.return_value = {
            "status": "success",
            "os": "Linux",
            "version": "1.0.0",
        }

        response = unauth_client.get("/api/info")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["info"]["os"] == "Linux"


def test_get_themes_success(unauth_client: TestClient, tmp_path, app_context):
    themes_dir = tmp_path / "themes"
    themes_dir.mkdir()
    (themes_dir / "custom1.css").touch()
    app_context.settings.set("paths.themes", str(themes_dir))

    response = unauth_client.get("/api/info/themes")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "custom1" in data["themes"]
    assert "default" == data["themes"][0]


def test_post_add_players_success(admin_auth_client: TestClient):
    with patch(
        "bedrock_server_manager.api.player.add_players_manually_api"
    ) as mock_add:
        mock_add.return_value = {
            "status": "success",
            "message": "Added 1 player",
            "count": 1,
        }

        response = admin_auth_client.post(
            "/api/players/add", json={"players": ["123456789,Steve"]}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["count"] == 1
