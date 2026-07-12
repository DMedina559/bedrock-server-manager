"""
Integration tests for the backup_restore router endpoints.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient


def test_put_prune_backups_success(admin_auth_client: TestClient, real_bedrock_server):
    with patch(
        "bedrock_server_manager.web.tasks.TaskManager.run_task"
    ) as mock_run_task:
        mock_run_task.return_value = "test_task_id"
        response = admin_auth_client.put(
            f"/api/server/{real_bedrock_server.server_name}/backups/prune"
        )
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "pending"
        assert data["task_id"] == "test_task_id"


def test_get_list_server_backups_world_success(
    admin_auth_client: TestClient, real_bedrock_server
):
    with patch(
        "bedrock_server_manager.api.backup_restore.list_backup_files"
    ) as mock_api:
        mock_api.return_value = {
            "status": "success",
            "backups": ["/path/to/backup1.zip", "/path/to/backup2.zip"],
        }
        response = admin_auth_client.get(
            f"/api/server/{real_bedrock_server.server_name}/backup/list/world"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["backups"] == ["backup1.zip", "backup2.zip"]


def test_get_list_server_backups_all_success(
    admin_auth_client: TestClient, real_bedrock_server
):
    with patch(
        "bedrock_server_manager.api.backup_restore.list_backup_files"
    ) as mock_api:
        mock_api.return_value = {
            "status": "success",
            "backups": {
                "world": ["/path/to/backup1.zip"],
                "properties": ["/path/to/props.bak"],
            },
        }
        response = admin_auth_client.get(
            f"/api/server/{real_bedrock_server.server_name}/backup/list/all"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["details"]["all_backups"]["world"] == ["backup1.zip"]
        assert data["details"]["all_backups"]["properties"] == ["props.bak"]


def test_get_list_server_backups_not_found(
    admin_auth_client: TestClient, real_bedrock_server
):
    with patch(
        "bedrock_server_manager.api.backup_restore.list_backup_files"
    ) as mock_api:
        mock_api.return_value = {
            "status": "error",
            "message": "Server backups not found.",
        }
        response = admin_auth_client.get(
            f"/api/server/{real_bedrock_server.server_name}/backup/list/world"
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]


def test_post_backup_action_world_success(
    admin_auth_client: TestClient, real_bedrock_server
):
    with patch(
        "bedrock_server_manager.web.tasks.TaskManager.run_task"
    ) as mock_run_task:
        mock_run_task.return_value = "test_task_id"
        response = admin_auth_client.post(
            f"/api/server/{real_bedrock_server.server_name}/backup/action",
            json={"backup_type": "world"},
        )
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "pending"
        assert data["task_id"] == "test_task_id"


def test_post_backup_action_config_missing_file(
    admin_auth_client: TestClient, real_bedrock_server
):
    response = admin_auth_client.post(
        f"/api/server/{real_bedrock_server.server_name}/backup/action",
        json={"backup_type": "config"},
    )
    assert response.status_code == 400
    assert "Missing or invalid 'file_to_backup'" in response.json()["detail"]


def test_post_restore_action_all_success(
    admin_auth_client: TestClient, real_bedrock_server
):
    with patch(
        "bedrock_server_manager.web.tasks.TaskManager.run_task"
    ) as mock_run_task:
        mock_run_task.return_value = "test_task_id"
        response = admin_auth_client.post(
            f"/api/server/{real_bedrock_server.server_name}/restore/action",
            json={"restore_type": "all"},
        )
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "pending"
        assert data["task_id"] == "test_task_id"


def test_post_restore_action_world_success(
    admin_auth_client: TestClient, app_context, tmp_path, real_bedrock_server
):
    backups_dir = tmp_path / "backups"
    server_backups_dir = backups_dir / real_bedrock_server.server_name
    server_backups_dir.mkdir(parents=True)
    backup_file = server_backups_dir / "world_backup.zip"
    backup_file.touch()

    app_context.settings.set("paths.backups", str(backups_dir))

    with patch(
        "bedrock_server_manager.web.tasks.TaskManager.run_task"
    ) as mock_run_task:
        mock_run_task.return_value = "test_task_id"
        response = admin_auth_client.post(
            f"/api/server/{real_bedrock_server.server_name}/restore/action",
            json={"restore_type": "world", "backup_file": "world_backup.zip"},
        )
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "pending"
        assert data["task_id"] == "test_task_id"


def test_post_restore_action_invalid_type(
    admin_auth_client: TestClient, real_bedrock_server
):
    response = admin_auth_client.post(
        f"/api/server/{real_bedrock_server.server_name}/restore/action",
        json={"restore_type": "invalid_type", "backup_file": "world_backup.zip"},
    )
    assert response.status_code == 400
    assert "Invalid 'restore_type'" in response.json()["detail"]


def test_post_restore_action_path_traversal(
    admin_auth_client: TestClient, app_context, tmp_path, real_bedrock_server
):
    backups_dir = tmp_path / "backups"
    app_context.settings.set("paths.backups", str(backups_dir))

    response = admin_auth_client.post(
        f"/api/server/{real_bedrock_server.server_name}/restore/action",
        json={"restore_type": "world", "backup_file": "../../etc/passwd"},
    )
    assert response.status_code == 400
    assert "Invalid 'backup_file' path" in response.json()["detail"]


def test_post_restore_action_file_not_found(
    admin_auth_client: TestClient, app_context, tmp_path, real_bedrock_server
):
    backups_dir = tmp_path / "backups"
    server_backups_dir = backups_dir / real_bedrock_server.server_name
    server_backups_dir.mkdir(parents=True)
    app_context.settings.set("paths.backups", str(backups_dir))

    response = admin_auth_client.post(
        f"/api/server/{real_bedrock_server.server_name}/restore/action",
        json={"restore_type": "world", "backup_file": "missing.zip"},
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]
