import pytest
from unittest.mock import patch, MagicMock


def test_backup_server_api_route_success(authenticated_client, real_bedrock_server):
    """Test the backup_server_api_route with a successful backup."""
    app_context = authenticated_client.app.state.app_context
    app_context.task_manager.run_task = MagicMock(return_value="backup-task-id")

    response = authenticated_client.post(
        f"/api/server/{real_bedrock_server.server_name}/backup/action",
        json={"backup_type": "all"},
    )
    assert response.status_code == 202
    json_data = response.json()
    assert json_data["status"] == "pending"
    assert json_data["task_id"] == "backup-task-id"
    app_context.task_manager.run_task.assert_called_once()


def test_get_backups_api_route_success(authenticated_client, real_bedrock_server):
    """Test the get_backups_api_route with a successful backup list."""
    response = authenticated_client.get(
        f"/api/server/{real_bedrock_server.server_name}/backup/list/all"
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"


@patch("bedrock_server_manager.api.backup_restore.list_backup_files")
def test_get_backups_api_route_no_backups(mock_get_backups, authenticated_client):
    """Test the get_backups_api_route with no backups."""
    app_context = MagicMock()
    authenticated_client.app.state.app_context = app_context
    mock_get_backups.return_value = {"status": "success", "backups": {}}
    response = authenticated_client.get("/api/server/test-server/backup/list/all")
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert response.json()["details"]["all_backups"] == {}


def test_restore_backup_api_route_success(authenticated_client, real_bedrock_server):
    """Test the restore_backup_api_route with a successful restore."""
    app_context = authenticated_client.app.state.app_context
    app_context.task_manager.run_task = MagicMock(return_value="restore-task-id")

    # Mock the os.path.isfile check to prevent failure on non-existent backup file
    with patch("os.path.isfile", return_value=True):
        response = authenticated_client.post(
            f"/api/server/{real_bedrock_server.server_name}/restore/action",
            json={"restore_type": "world", "backup_file": "test.zip"},
        )
    assert response.status_code == 202
    json_data = response.json()
    assert json_data["status"] == "pending"
    assert json_data["task_id"] == "restore-task-id"
    app_context.task_manager.run_task.assert_called_once()
