import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from bedrock_server_manager.web.main import app
from bedrock_server_manager.web.dependencies import validate_server_exists
from bedrock_server_manager.web.auth_utils import create_access_token
from datetime import timedelta
import os

# Test data
TEST_USER = "testuser"


@pytest.fixture
def client():
    """Create a test client for the app, with authentication and mocked dependencies."""
    os.environ["BEDROCK_SERVER_MANAGER_USERNAME"] = TEST_USER
    os.environ["BEDROCK_SERVER_MANAGER_PASSWORD"] = "testpassword"
    os.environ["BEDROCK_SERVER_MANAGER_SECRET_KEY"] = "test-secret-key"

    app.dependency_overrides[validate_server_exists] = lambda: "test-server"

    access_token = create_access_token(
        data={"sub": TEST_USER}, expires_delta=timedelta(minutes=15)
    )
    client = TestClient(app)
    client.headers["Authorization"] = f"Bearer {access_token}"

    yield client

    del os.environ["BEDROCK_SERVER_MANAGER_USERNAME"]
    del os.environ["BEDROCK_SERVER_MANAGER_PASSWORD"]
    del os.environ["BEDROCK_SERVER_MANAGER_SECRET_KEY"]
    app.dependency_overrides = {}


@patch("bedrock_server_manager.web.routers.backup_restore.tasks.run_task")
@patch("bedrock_server_manager.web.routers.backup_restore.tasks.create_task")
@patch("bedrock_server_manager.api.backup_restore.backup_all")
def test_backup_server_api_route_success(
    mock_backup, mock_create_task, mock_run_task, client
):
    """Test the backup_server_api_route with a successful backup."""
    mock_create_task.return_value = "test_task_id"
    mock_backup.return_value = {"status": "success"}
    response = client.post(
        "/api/server/test-server/backup/action", json={"backup_type": "all"}
    )
    assert response.status_code == 202
    assert response.json()["status"] == "pending"
    assert response.json()["task_id"] == "test_task_id"


@patch("bedrock_server_manager.web.routers.backup_restore.tasks.run_task")
@patch("bedrock_server_manager.web.routers.backup_restore.tasks.create_task")
@patch("bedrock_server_manager.api.backup_restore.backup_all")
def test_backup_server_api_route_failure(
    mock_backup, mock_create_task, mock_run_task, client
):
    """Test the backup_server_api_route with a failed backup."""
    from bedrock_server_manager.error import BSMError

    mock_create_task.return_value = "test_task_id"
    mock_run_task.side_effect = BSMError("Backup failed")

    with pytest.raises(BSMError):
        client.post(
            "/api/server/test-server/backup/action", json={"backup_type": "all"}
        )


@patch("bedrock_server_manager.api.backup_restore.list_backup_files")
def test_get_backups_api_route_success(mock_get_backups, client):
    """Test the get_backups_api_route with a successful backup list."""
    mock_get_backups.return_value = {"status": "success", "backups": []}
    response = client.get("/api/server/test-server/backup/list/all")
    assert response.status_code == 200
    assert response.json()["status"] == "success"


@patch("bedrock_server_manager.api.backup_restore.list_backup_files")
def test_get_backups_api_route_no_backups(mock_get_backups, client):
    """Test the get_backups_api_route with no backups."""
    mock_get_backups.return_value = {"status": "success", "backups": {}}
    response = client.get("/api/server/test-server/backup/list/all")
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert response.json()["details"]["all_backups"] == {}


@patch("bedrock_server_manager.web.routers.backup_restore.tasks.run_task")
@patch("bedrock_server_manager.web.routers.backup_restore.tasks.create_task")
@patch("bedrock_server_manager.api.backup_restore.restore_all")
def test_restore_backup_api_route_success(
    mock_restore, mock_create_task, mock_run_task, client
):
    """Test the restore_backup_api_route with a successful restore."""
    mock_create_task.return_value = "test_task_id"
    mock_restore.return_value = {"status": "success"}
    response = client.post(
        "/api/server/test-server/restore/action", json={"restore_type": "all"}
    )
    assert response.status_code == 202
    assert response.json()["status"] == "pending"
    assert response.json()["task_id"] == "test_task_id"


@patch("bedrock_server_manager.web.routers.backup_restore.tasks.run_task")
@patch("bedrock_server_manager.web.routers.backup_restore.tasks.create_task")
@patch("bedrock_server_manager.api.backup_restore.restore_all")
def test_restore_backup_api_route_failure(
    mock_restore, mock_create_task, mock_run_task, client
):
    """Test the restore_backup_api_route with a failed restore."""
    from bedrock_server_manager.error import BSMError

    mock_create_task.return_value = "test_task_id"
    mock_run_task.side_effect = BSMError("Restore failed")
    with pytest.raises(BSMError):
        client.post(
            "/api/server/test-server/restore/action", json={"restore_type": "all"}
        )


@patch("bedrock_server_manager.web.routers.backup_restore.tasks.run_task")
@patch("bedrock_server_manager.web.routers.backup_restore.tasks.create_task")
@patch("bedrock_server_manager.api.backup_restore.backup_all")
def test_backup_in_progress(mock_backup, mock_create_task, mock_run_task, client):
    """Test that a 423 is returned when a backup is in progress."""
    from bedrock_server_manager.error import BSMError

    mock_create_task.return_value = "test_task_id"
    mock_run_task.side_effect = BSMError(
        "Backup/restore operation already in progress."
    )
    with pytest.raises(BSMError):
        client.post(
            "/api/server/test-server/backup/action", json={"backup_type": "all"}
        )
