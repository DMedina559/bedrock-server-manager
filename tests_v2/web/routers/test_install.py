"""
Integration tests for the install router endpoints.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient


def test_get_custom_zips_unauthorized(unauth_client: TestClient):
    response = unauth_client.get("/api/downloads/list")
    assert response.status_code == 401


def test_get_custom_zips_success(admin_auth_client: TestClient):
    with patch("bedrock_server_manager.web.routers.install.find_files") as mock_find:
        with patch("os.path.isdir", return_value=True):
            mock_find.return_value = [
                "/path/to/custom/test.zip",
                "/path/to/custom/another.zip",
            ]
            response = admin_auth_client.get("/api/downloads/list")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert "test.zip" in data["custom_zips"]
            assert "another.zip" in data["custom_zips"]


def test_get_custom_zips_no_dir(admin_auth_client: TestClient):
    with patch("os.path.isdir", return_value=False):
        response = admin_auth_client.get("/api/downloads/list")
        assert response.status_code == 200
        assert response.json()["custom_zips"] == []


def test_get_custom_zips_error(admin_auth_client: TestClient):
    with patch(
        "bedrock_server_manager.web.routers.install.find_files",
        side_effect=Exception("Disk error"),
    ):
        with patch("os.path.isdir", return_value=True):
            response = admin_auth_client.get("/api/downloads/list")
            assert response.status_code == 500


def test_post_install_server_unauthorized(unauth_client: TestClient):
    response = unauth_client.post(
        "/api/server/install",
        json={"server_name": "TestServer", "server_version": "LATEST"},
    )
    assert response.status_code == 401


def test_post_install_server_forbidden(auth_client: TestClient):
    response = auth_client.post(
        "/api/server/install",
        json={"server_name": "TestServer", "server_version": "LATEST"},
    )
    assert response.status_code == 403


def test_post_install_server_success(admin_auth_client: TestClient):
    with patch(
        "bedrock_server_manager.utils.server.validate_server", return_value=False
    ):
        with patch(
            "bedrock_server_manager.web.tasks.TaskManager.run_task",
            return_value="task-123",
        ):
            response = admin_auth_client.post(
                "/api/server/install",
                json={"server_name": "NewServer", "server_version": "LATEST"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "pending"
            assert data["task_id"] == "task-123"


def test_post_install_server_exists_no_overwrite(admin_auth_client: TestClient):
    with patch(
        "bedrock_server_manager.utils.server.validate_server", return_value=True
    ):
        response = admin_auth_client.post(
            "/api/server/install",
            json={
                "server_name": "ExistingServer",
                "server_version": "LATEST",
                "overwrite": False,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "confirm_needed"
        assert data["server_name"] == "ExistingServer"


def test_post_install_server_exists_with_overwrite(admin_auth_client: TestClient):
    with patch(
        "bedrock_server_manager.utils.server.validate_server", return_value=True
    ):
        with patch(
            "bedrock_server_manager.web.routers.install.server_api.delete_server_data"
        ) as mock_delete:
            with patch(
                "bedrock_server_manager.web.tasks.TaskManager.run_task",
                return_value="task-456",
            ):
                mock_delete.return_value = {"status": "success"}
                response = admin_auth_client.post(
                    "/api/server/install",
                    json={
                        "server_name": "ExistingServer",
                        "server_version": "LATEST",
                        "overwrite": True,
                    },
                )
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "pending"
                assert data["task_id"] == "task-456"


def test_post_install_server_exists_with_overwrite_delete_fails(
    admin_auth_client: TestClient,
):
    with patch(
        "bedrock_server_manager.utils.server.validate_server", return_value=True
    ):
        with patch(
            "bedrock_server_manager.web.routers.install.server_api.delete_server_data"
        ) as mock_delete:
            mock_delete.return_value = {
                "status": "error",
                "message": "Failed to delete files",
            }
            response = admin_auth_client.post(
                "/api/server/install",
                json={
                    "server_name": "ExistingServer",
                    "server_version": "LATEST",
                    "overwrite": True,
                },
            )
            assert response.status_code == 500


def test_post_install_server_custom_version_no_zip(admin_auth_client: TestClient):
    with patch(
        "bedrock_server_manager.utils.server.validate_server", return_value=False
    ):
        response = admin_auth_client.post(
            "/api/server/install",
            json={"server_name": "CustomServer", "server_version": "CUSTOM"},
        )
        assert response.status_code == 400


def test_post_install_server_custom_version_success(admin_auth_client: TestClient):
    with patch(
        "bedrock_server_manager.utils.server.validate_server", return_value=False
    ):
        with patch(
            "bedrock_server_manager.web.tasks.TaskManager.run_task",
            return_value="task-custom",
        ):
            response = admin_auth_client.post(
                "/api/server/install",
                json={
                    "server_name": "CustomServer",
                    "server_version": "CUSTOM",
                    "server_zip_path": "my_custom.zip",
                },
            )
            assert response.status_code == 200
            assert response.json()["status"] == "pending"


def test_post_install_server_invalid_name(admin_auth_client: TestClient):
    response = admin_auth_client.post(
        "/api/server/install",
        json={"server_name": "Invalid Server Name!", "server_version": "LATEST"},
    )
    assert response.status_code == 400
