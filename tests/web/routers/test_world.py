"""
Integration tests for the world router endpoints.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient


def test_get_worlds_list_unauthorized(unauth_client: TestClient):
    response = unauth_client.get("/api/content/worlds")
    assert response.status_code == 401


def test_get_worlds_list_success(admin_auth_client: TestClient):
    with patch(
        "bedrock_server_manager.web.routers.world.app_api.list_available_worlds_api"
    ) as mock_list:
        mock_list.return_value = {
            "status": "success",
            "files": ["/path/world1.mcworld", "/path/world2.mcworld"],
        }

        response = admin_auth_client.get("/api/content/worlds")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert len(data["files"]) == 2
        assert "world1.mcworld" in data["files"]


def test_get_worlds_list_error(admin_auth_client: TestClient):
    with patch(
        "bedrock_server_manager.web.routers.world.app_api.list_available_worlds_api"
    ) as mock_list:
        mock_list.return_value = {"status": "error", "message": "Disk unavailable"}

        response = admin_auth_client.get("/api/content/worlds")
        assert response.status_code == 500
        assert "Disk unavailable" in response.json()["detail"]


def test_post_world_install_success(
    admin_auth_client: TestClient, real_bedrock_server, app_context, tmp_path
):
    # Set up mock content dir
    app_context.settings.set("paths.content", str(tmp_path))
    worlds_dir = tmp_path / "worlds"
    worlds_dir.mkdir(parents=True, exist_ok=True)
    target_file = worlds_dir / "my_world.mcworld"
    target_file.touch()

    with patch(
        "bedrock_server_manager.utils.server.validate_server", return_value=True
    ):
        with patch(
            "bedrock_server_manager.web.tasks.TaskManager.run_task",
            return_value="task-123",
        ):
            response = admin_auth_client.post(
                f"/api/server/{real_bedrock_server.server_name}/world/install",
                json={"filename": "my_world.mcworld"},
            )
            assert response.status_code == 202
            assert response.json()["task_id"] == "task-123"


def test_post_world_install_not_found(
    admin_auth_client: TestClient, real_bedrock_server, app_context, tmp_path
):
    app_context.settings.set("paths.content", str(tmp_path))
    worlds_dir = tmp_path / "worlds"
    worlds_dir.mkdir(parents=True, exist_ok=True)

    with patch(
        "bedrock_server_manager.utils.server.validate_server", return_value=True
    ):
        response = admin_auth_client.post(
            f"/api/server/{real_bedrock_server.server_name}/world/install",
            json={"filename": "missing.mcworld"},
        )
        assert response.status_code == 404


def test_post_world_install_path_traversal(
    admin_auth_client: TestClient, real_bedrock_server, app_context, tmp_path
):
    app_context.settings.set("paths.content", str(tmp_path))
    worlds_dir = tmp_path / "worlds"
    worlds_dir.mkdir(parents=True, exist_ok=True)

    with patch(
        "bedrock_server_manager.utils.server.validate_server", return_value=True
    ):
        response = admin_auth_client.post(
            f"/api/server/{real_bedrock_server.server_name}/world/install",
            json={"filename": "../../../etc/passwd"},
        )
        assert response.status_code == 400


def test_post_world_export_success(admin_auth_client: TestClient, real_bedrock_server):
    with patch(
        "bedrock_server_manager.utils.server.validate_server", return_value=True
    ):
        with patch(
            "bedrock_server_manager.web.tasks.TaskManager.run_task",
            return_value="task-456",
        ):
            response = admin_auth_client.post(
                f"/api/server/{real_bedrock_server.server_name}/world/export"
            )
            assert response.status_code == 202
            assert response.json()["task_id"] == "task-456"


def test_delete_world_reset_success(admin_auth_client: TestClient, real_bedrock_server):
    with patch(
        "bedrock_server_manager.utils.server.validate_server", return_value=True
    ):
        with patch(
            "bedrock_server_manager.web.tasks.TaskManager.run_task",
            return_value="task-789",
        ):

            response = admin_auth_client.request(
                "DELETE", f"/api/server/{real_bedrock_server.server_name}/world/reset"
            )
            assert response.status_code == 202
            assert response.json()["task_id"] == "task-789"


def test_get_world_icon_success(
    unauth_client: TestClient, real_bedrock_server, tmp_path
):
    icon_path = tmp_path / "world_icon.jpeg"
    icon_path.write_bytes(b"icon_data")

    with patch(
        "bedrock_server_manager.context.AppContext.get_server"
    ) as mock_get_server:
        mock_server = mock_get_server.return_value
        mock_server.has_world_icon.return_value = True
        mock_server.world_icon_filesystem_path = str(icon_path)

        response = unauth_client.get(
            f"/api/server/{real_bedrock_server.server_name}/world/icon"
        )
        assert response.status_code == 200


def test_get_world_icon_fallback(
    unauth_client: TestClient, real_bedrock_server, tmp_path
):
    fallback_icon = tmp_path / "image" / "icon" / "favicon.ico"
    fallback_icon.parent.mkdir(parents=True, exist_ok=True)
    fallback_icon.write_bytes(b"favicon")

    with patch(
        "bedrock_server_manager.context.AppContext.get_server"
    ) as mock_get_server:
        mock_server = mock_get_server.return_value
        mock_server.has_world_icon.return_value = False

        with patch(
            "bedrock_server_manager.web.routers.world.STATIC_DIR", str(tmp_path)
        ):
            response = unauth_client.get(
                f"/api/server/{real_bedrock_server.server_name}/world/icon"
            )
            assert response.status_code == 200
