"""
Integration tests for the api_info router endpoints.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient

from bedrock_server_manager.api.models import (
    AddPlayersManuallyResponse,
    GetAllKnownPlayersResponse,
    GetAllServersDataResponse,
    GetBedrockProcessInfoResponse,
    GetServerRunningStatusResponse,
    GetSystemAndAppInfoResponse,
    PruneDownloadCacheResponse,
    ScanAndUpdatePlayerDbResponse,
)
from bedrock_server_manager.error import BSMError


def test_get_server_running_status_success(
    auth_client: TestClient, real_bedrock_server
):
    with patch(
        "bedrock_server_manager.api.system.get_server_running_status"
    ) as mock_status:
        mock_status.return_value = GetServerRunningStatusResponse.model_validate(
            {"status": "success", "is_running": True, "message": "Server is running."}
        )

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
        assert response.json()["error"]["message"] == "An unexpected error occurred."


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
        mock_info.return_value = GetBedrockProcessInfoResponse.model_validate(
            {
                "status": "success",
                "process_info": {
                    "pid": 1234,
                    "cpu_percent": 10.5,
                    "memory_mb": 1024.0,
                    "uptime": "0:01:00",
                },
            }
        )

        response = auth_client.get(
            f"/api/server/{real_bedrock_server.server_name}/process_info"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["process_info"]["cpu_percent"] == 10.5


def test_put_scan_players_success(admin_auth_client: TestClient):
    with patch(
        "bedrock_server_manager.api.player.scan_and_update_player_db"
    ) as mock_scan:
        mock_scan.return_value = ScanAndUpdatePlayerDbResponse.model_validate(
            {
                "status": "success",
                "message": "Scanned 1 player",
                "details": {
                    "total_entries_in_logs": 1,
                    "unique_players_submitted_for_saving": 1,
                    "actually_saved_or_updated_in_db": 1,
                    "scan_errors": [],
                },
            }
        )

        response = admin_auth_client.put("/api/players/scan")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["details"]["actually_saved_or_updated_in_db"] == 1


def test_get_all_players_success(admin_auth_client: TestClient):
    with patch("bedrock_server_manager.api.player.get_all_known_players") as mock_get:
        mock_get.return_value = GetAllKnownPlayersResponse.model_validate(
            {
                "status": "success",
                "players": [{"xuid": "123", "name": "Steve"}],
                "message": "Success",
            }
        )

        response = admin_auth_client.get("/api/players/get")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert len(data["players"]) == 1


async def test_put_prune_downloads_success(
    admin_auth_client: TestClient, tmp_path, app_context
):
    downloads_dir = tmp_path / "downloads"
    downloads_dir.mkdir()
    target_dir = downloads_dir / "test_target"
    target_dir.mkdir()
    await app_context.settings.set("paths.downloads", str(downloads_dir))

    with patch("bedrock_server_manager.api.misc.prune_download_cache") as mock_prune:
        mock_prune.return_value = PruneDownloadCacheResponse.model_validate(
            {"status": "success", "message": "Pruned old downloads."}
        )

        response = admin_auth_client.put(
            "/api/downloads/prune", json={"directory": "test_target", "keep": 1}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["message"] == "Pruned old downloads."


async def test_put_prune_downloads_invalid_path(
    admin_auth_client: TestClient, tmp_path, app_context
):
    downloads_dir = tmp_path / "downloads"
    downloads_dir.mkdir()
    await app_context.settings.set("paths.downloads", str(downloads_dir))

    response = admin_auth_client.put(
        "/api/downloads/prune", json={"directory": "../../etc/passwd", "keep": 1}
    )

    assert response.status_code == 400


def test_get_servers_list_success(auth_client: TestClient):
    from unittest.mock import AsyncMock

    with patch(
        "bedrock_server_manager.api.application.get_all_servers_data",
        new_callable=AsyncMock,
    ) as mock_list:
        mock_list.return_value = GetAllServersDataResponse.model_validate(
            {
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
        )

        response = auth_client.get("/api/servers")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert len(data["servers"]) == 1


def test_get_system_info_success(unauth_client: TestClient):
    with patch(
        "bedrock_server_manager.api.application.get_system_and_app_info"
    ) as mock_info:
        mock_info.return_value = GetSystemAndAppInfoResponse.model_validate(
            {
                "status": "success",
                "os_type": "Linux",
                "app_version": "1.0.0",
                "splash_text": "Welcome",
            }
        )

        response = unauth_client.get("/api/info")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["info"]["os_type"] == "Linux"


async def test_get_themes_success(unauth_client: TestClient, tmp_path, app_context):
    themes_dir = tmp_path / "themes"
    themes_dir.mkdir()
    (themes_dir / "custom1.css").touch()
    await app_context.settings.set("paths.themes", str(themes_dir))

    response = unauth_client.get("/api/info/themes")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "custom1" in data["themes"]
    assert "default" == data["themes"][0]


def test_post_add_players_success(admin_auth_client: TestClient):
    with patch("bedrock_server_manager.api.player.add_players_manually") as mock_add:
        mock_add.return_value = AddPlayersManuallyResponse.model_validate(
            {"status": "success", "message": "Added 1 player", "count": 1}
        )

        response = admin_auth_client.post(
            "/api/players/add", json={"players": ["123456789,Steve"]}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["count"] == 1
