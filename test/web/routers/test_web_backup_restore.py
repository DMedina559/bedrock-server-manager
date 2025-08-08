import pytest
from unittest.mock import patch, MagicMock


@patch("bedrock_server_manager.web.routers.backup_restore.tasks.run_task")
@patch("bedrock_server_manager.web.routers.backup_restore.tasks.create_task")
def test_backup_server_api_route_success(
    mock_create_task, mock_run_task, authenticated_client
):
    """Test the backup_server_api_route with a successful backup."""
    app_context = MagicMock()
    authenticated_client.app.state.app_context = app_context
    mock_create_task.return_value = "test_task_id"
    response = authenticated_client.post(
        "/api/server/test-server/backup/action", json={"backup_type": "all"}
    )
    assert response.status_code == 202
    assert response.json()["status"] == "pending"
    assert response.json()["task_id"] == "test_task_id"


@patch("bedrock_server_manager.web.routers.backup_restore.tasks.run_task")
@patch("bedrock_server_manager.web.routers.backup_restore.tasks.create_task")
def test_backup_server_api_route_failure(
    mock_create_task, mock_run_task, authenticated_client
):
    """Test the backup_server_api_route with a failed backup."""
    from bedrock_server_manager.error import BSMError

    app_context = MagicMock()
    authenticated_client.app.state.app_context = app_context
    mock_create_task.return_value = "test_task_id"
    mock_run_task.side_effect = BSMError("Backup failed")

    with pytest.raises(BSMError):
        authenticated_client.post(
            "/api/server/test-server/backup/action", json={"backup_type": "all"}
        )


@patch("bedrock_server_manager.api.backup_restore.list_backup_files")
def test_get_backups_api_route_success(mock_get_backups, authenticated_client):
    """Test the get_backups_api_route with a successful backup list."""
    app_context = MagicMock()
    authenticated_client.app.state.app_context = app_context
    mock_get_backups.return_value = {"status": "success", "backups": []}
    response = authenticated_client.get("/api/server/test-server/backup/list/all")
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    mock_get_backups.assert_called_once_with(
        server_name="test-server", backup_type="all", app_context=app_context
    )


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


@patch("bedrock_server_manager.web.routers.backup_restore.tasks.run_task")
@patch("bedrock_server_manager.web.routers.backup_restore.tasks.create_task")
def test_restore_backup_api_route_success(
    mock_create_task, mock_run_task, authenticated_client
):
    """Test the restore_backup_api_route with a successful restore."""
    app_context = MagicMock()
    app_context.settings.get.return_value = "test"
    authenticated_client.app.state.app_context = app_context
    mock_create_task.return_value = "test_task_id"
    response = authenticated_client.post(
        "/api/server/test-server/restore/action", json={"restore_type": "all"}
    )
    assert response.status_code == 202
    assert response.json()["status"] == "pending"
    assert response.json()["task_id"] == "test_task_id"


@patch("bedrock_server_manager.web.routers.backup_restore.tasks.run_task")
@patch("bedrock_server_manager.web.routers.backup_restore.tasks.create_task")
def test_restore_backup_api_route_failure(
    mock_create_task, mock_run_task, authenticated_client
):
    """Test the restore_backup_api_route with a failed restore."""
    from bedrock_server_manager.error import BSMError

    app_context = MagicMock()
    app_context.settings.get.return_value = "test"
    authenticated_client.app.state.app_context = app_context
    mock_create_task.return_value = "test_task_id"
    mock_run_task.side_effect = BSMError("Restore failed")
    with pytest.raises(BSMError):
        authenticated_client.post(
            "/api/server/test-server/restore/action", json={"restore_type": "all"}
        )


@patch("bedrock_server_manager.web.routers.backup_restore.tasks.run_task")
@patch("bedrock_server_manager.web.routers.backup_restore.tasks.create_task")
def test_backup_in_progress(mock_create_task, mock_run_task, authenticated_client):
    """Test that a 423 is returned when a backup is in progress."""
    from bedrock_server_manager.error import BSMError

    app_context = MagicMock()
    authenticated_client.app.state.app_context = app_context
    mock_create_task.return_value = "test_task_id"
    mock_run_task.side_effect = BSMError(
        "Backup/restore operation already in progress."
    )
    with pytest.raises(BSMError):
        authenticated_client.post(
            "/api/server/test-server/backup/action", json={"backup_type": "all"}
        )
