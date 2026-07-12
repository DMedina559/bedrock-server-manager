"""
Integration tests for the addon router endpoints.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient

from bedrock_server_manager.context import AppContext


def test_get_addons_unauthorized(unauth_client: TestClient):
    """Test getting addons without authentication."""
    response = unauth_client.get("/api/content/addons")
    assert response.status_code == 401


def test_get_addons_success(admin_auth_client: TestClient):
    """Test getting available addons with admin permissions."""
    with patch("bedrock_server_manager.api.addon.list_available_addons") as mock_api:
        mock_api.return_value = {
            "status": "success",
            "files": ["/path/to/addon1.mcaddon", "/path/to/addon2.mcpack"],
        }
        response = admin_auth_client.get("/api/content/addons")
        assert response.status_code == 200
        assert response.json()["files"] == ["addon1.mcaddon", "addon2.mcpack"]


def test_get_server_addons_success(
    admin_auth_client: TestClient, app_context: AppContext, real_bedrock_server
):
    """Test getting installed addons for a specific server."""
    with patch("bedrock_server_manager.api.addon.list_installed_addons") as mock_api:
        mock_api.return_value = {
            "status": "success",
            "addons": {
                "behavior_packs": [
                    {
                        "uuid": "123",
                        "name": "Test BP",
                        "version": [1, 0, 0],
                        "status": "active",
                    }
                ],
                "resource_packs": [],
            },
        }
        response = admin_auth_client.get(
            f"/api/server/{real_bedrock_server.server_name}/addons"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert len(data["addons"]["behavior_packs"]) == 1
        assert data["addons"]["behavior_packs"][0]["uuid"] == "123"


def test_post_enable_addon_success(
    admin_auth_client: TestClient, app_context: AppContext, real_bedrock_server
):
    """Test enabling an addon."""
    with patch(
        "bedrock_server_manager.web.tasks.TaskManager.run_task"
    ) as mock_run_task:
        mock_run_task.return_value = "test_task_id"
        response = admin_auth_client.post(
            f"/api/server/{real_bedrock_server.server_name}/addon/enable",
            json={"pack_uuid": "123-abc", "pack_type": "behavior"},
        )
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "pending"
        assert data["task_id"] == "test_task_id"


def test_post_disable_addon_success(
    admin_auth_client: TestClient, app_context: AppContext, real_bedrock_server
):
    """Test disabling an addon."""
    with patch(
        "bedrock_server_manager.web.tasks.TaskManager.run_task"
    ) as mock_run_task:
        mock_run_task.return_value = "test_task_id"
        response = admin_auth_client.post(
            f"/api/server/{real_bedrock_server.server_name}/addon/disable",
            json={"pack_uuid": "123-abc", "pack_type": "behavior"},
        )
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "pending"
        assert data["task_id"] == "test_task_id"


def test_post_update_subpack_success(
    admin_auth_client: TestClient, app_context: AppContext, real_bedrock_server
):
    """Test updating a subpack."""
    with patch(
        "bedrock_server_manager.web.tasks.TaskManager.run_task"
    ) as mock_run_task:
        mock_run_task.return_value = "test_task_id"
        response = admin_auth_client.post(
            f"/api/server/{real_bedrock_server.server_name}/addon/subpack",
            json={
                "pack_uuid": "123-abc",
                "pack_type": "behavior",
                "subpack_name": "new_subpack",
            },
        )
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "pending"
        assert data["task_id"] == "test_task_id"


def test_delete_uninstall_addon_success(
    admin_auth_client: TestClient, app_context: AppContext, real_bedrock_server
):
    """Test uninstalling an addon."""
    with patch(
        "bedrock_server_manager.web.tasks.TaskManager.run_task"
    ) as mock_run_task:
        mock_run_task.return_value = "test_task_id"
        response = admin_auth_client.request(
            "DELETE",
            f"/api/server/{real_bedrock_server.server_name}/addon/uninstall",
            json={"pack_uuid": "123-abc", "pack_type": "behavior"},
        )
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "pending"
        assert data["task_id"] == "test_task_id"


def test_post_reorder_addons_success(
    admin_auth_client: TestClient, app_context: AppContext, real_bedrock_server
):
    """Test reordering addons."""
    with patch(
        "bedrock_server_manager.web.tasks.TaskManager.run_task"
    ) as mock_run_task:
        mock_run_task.return_value = "test_task_id"
        response = admin_auth_client.post(
            f"/api/server/{real_bedrock_server.server_name}/addon/reorder",
            json={"uuids": ["123", "456"], "pack_type": "behavior"},
        )
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "pending"
        assert data["task_id"] == "test_task_id"


def test_post_install_addon_success(
    admin_auth_client: TestClient,
    app_context: AppContext,
    real_bedrock_server,
    tmp_path,
):
    """Test installing an addon from a file."""
    # Setup mock addon file
    content_dir = tmp_path / "test_data" / "content" / "addons"
    content_dir.mkdir(parents=True, exist_ok=True)
    addon_file = content_dir / "test_addon.mcaddon"
    addon_file.touch()

    # Update app_context settings to point to our temp dir
    app_context.settings.set("paths.content", str(tmp_path / "test_data" / "content"))

    with patch(
        "bedrock_server_manager.web.tasks.TaskManager.run_task"
    ) as mock_run_task:
        mock_run_task.return_value = "test_task_id"
        response = admin_auth_client.post(
            f"/api/server/{real_bedrock_server.server_name}/addon/install",
            json={"filename": "test_addon.mcaddon"},
        )
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "pending"
        assert data["task_id"] == "test_task_id"


def test_post_install_addon_file_not_found(
    admin_auth_client: TestClient,
    app_context: AppContext,
    real_bedrock_server,
    tmp_path,
):
    """Test installing an addon where file does not exist."""
    app_context.settings.set("paths.content", str(tmp_path / "test_data" / "content"))

    response = admin_auth_client.post(
        f"/api/server/{real_bedrock_server.server_name}/addon/install",
        json={"filename": "nonexistent.mcaddon"},
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_post_install_addon_path_traversal(
    admin_auth_client: TestClient,
    app_context: AppContext,
    real_bedrock_server,
    tmp_path,
):
    """Test installing an addon with path traversal attack."""
    app_context.settings.set("paths.content", str(tmp_path / "test_data" / "content"))

    response = admin_auth_client.post(
        f"/api/server/{real_bedrock_server.server_name}/addon/install",
        json={"filename": "../../../etc/passwd"},
    )
    assert response.status_code == 400
    assert "Invalid file path" in response.json()["detail"]


def test_get_server_addon_icon_success(
    admin_auth_client: TestClient,
    app_context: AppContext,
    real_bedrock_server,
    tmp_path,
):
    """Test getting addon icon."""
    # Create a dummy icon file
    icon_path = tmp_path / "pack_icon.png"
    icon_path.touch()

    with patch("bedrock_server_manager.api.addon.list_installed_addons") as mock_api:
        mock_api.return_value = {
            "status": "success",
            "addons": {
                "behavior_packs": [
                    {
                        "uuid": "123",
                        "icon": str(icon_path),
                        "name": "Test BP",
                        "version": [1, 0, 0],
                        "status": "active",
                    }
                ]
            },
        }

        response = admin_auth_client.get(
            f"/api/server/{real_bedrock_server.server_name}/addon/icon?pack_type=behavior&uuid=123"
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"


def test_get_server_addon_icon_not_found_fallback(
    admin_auth_client: TestClient, app_context: AppContext, real_bedrock_server
):
    """Test getting addon icon that doesn't exist, checking fallback behavior."""
    with patch("bedrock_server_manager.api.addon.list_installed_addons") as mock_api:
        mock_api.return_value = {
            "status": "success",
            "addons": {
                "behavior_packs": [
                    {
                        "uuid": "123",
                        "name": "Test BP",
                        "version": [1, 0, 0],
                        "status": "active",
                    }
                ]  # no icon path
            },
        }

        with patch("os.path.isfile") as mock_isfile:
            # We must pretend the favicon exists to hit the fallback FileResponse code
            mock_isfile.return_value = True

            with patch("fastapi.responses.FileResponse") as mock_file_response:
                from fastapi import Response

                mock_file_response.return_value = Response(
                    content=b"dummy_icon", media_type="image/vnd.microsoft.icon"
                )

                response = admin_auth_client.get(
                    f"/api/server/{real_bedrock_server.server_name}/addon/icon?pack_type=behavior&uuid=123"
                )
                assert response.status_code == 200
