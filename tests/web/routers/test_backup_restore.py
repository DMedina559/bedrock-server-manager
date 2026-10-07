"""
Integration tests for the backup_restore router endpoints.
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from bedrock_server_manager.api.models import ListBackupFilesResponse
from bedrock_server_manager.error import AppFileNotFoundError


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
        assert data["status"] == "accepted"
        assert data["task_id"] == "test_task_id"


def test_get_list_server_backups_world_success(
    admin_auth_client: TestClient, real_bedrock_server
):
    with patch(
        "bedrock_server_manager.api.backup_restore.list_backup_files"
    ) as mock_api:
        mock_api.return_value = ListBackupFilesResponse.model_validate(
            {
                "status": "success",
                "backups": ["/path/to/backup1.zip", "/path/to/backup2.zip"],
            }
        )
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
        mock_api.return_value = ListBackupFilesResponse.model_validate(
            {
                "status": "success",
                "backups": {
                    "world": ["/path/to/backup1.zip"],
                    "properties": ["/path/to/props.bak"],
                },
            }
        )
        response = admin_auth_client.get(
            f"/api/server/{real_bedrock_server.server_name}/backup/list/all"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["backups"]["world"] == ["backup1.zip"]
        assert data["backups"]["properties"] == ["props.bak"]


def test_get_list_server_backups_not_found(
    admin_auth_client: TestClient, real_bedrock_server
):
    with patch(
        "bedrock_server_manager.api.backup_restore.list_backup_files"
    ) as mock_api:
        mock_api.side_effect = AppFileNotFoundError("Server backups not found.")
        response = admin_auth_client.get(
            f"/api/server/{real_bedrock_server.server_name}/backup/list/world"
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "not_found"


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
        assert data["status"] == "accepted"
        assert data["task_id"] == "test_task_id"


def test_post_backup_action_config_missing_file(
    admin_auth_client: TestClient, real_bedrock_server
):
    response = admin_auth_client.post(
        f"/api/server/{real_bedrock_server.server_name}/backup/action",
        json={"backup_type": "config"},
    )
    assert response.status_code == 400
    assert "Missing or invalid 'file_to_backup'" in response.json()["error"]["message"]


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
        assert data["status"] == "accepted"
        assert data["task_id"] == "test_task_id"


async def test_post_restore_action_world_success(
    admin_auth_client: TestClient, app_context, tmp_path, real_bedrock_server
):
    backups_dir = tmp_path / "backups"
    server_backups_dir = backups_dir / real_bedrock_server.server_name
    server_backups_dir.mkdir(parents=True)
    backup_file = server_backups_dir / "world_backup.zip"
    backup_file.touch()

    await app_context.settings.set("paths.backups", str(backups_dir))

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
        assert data["status"] == "accepted"
        assert data["task_id"] == "test_task_id"


def test_post_restore_action_invalid_type(
    admin_auth_client: TestClient, real_bedrock_server
):
    response = admin_auth_client.post(
        f"/api/server/{real_bedrock_server.server_name}/restore/action",
        json={"restore_type": "invalid_type", "backup_file": "world_backup.zip"},
    )
    assert response.status_code == 400
    assert "Invalid 'restore_type'" in response.json()["error"]["message"]


async def test_post_restore_action_path_traversal(
    admin_auth_client: TestClient, app_context, tmp_path, real_bedrock_server
):
    backups_dir = tmp_path / "backups"
    await app_context.settings.set("paths.backups", str(backups_dir))

    response = admin_auth_client.post(
        f"/api/server/{real_bedrock_server.server_name}/restore/action",
        json={"restore_type": "world", "backup_file": "../../etc/passwd"},
    )
    assert response.status_code == 400
    assert "Invalid 'backup_file' path" in response.json()["error"]["message"]


async def test_post_restore_action_file_not_found(
    admin_auth_client: TestClient, app_context, tmp_path, real_bedrock_server
):
    backups_dir = tmp_path / "backups"
    server_backups_dir = backups_dir / real_bedrock_server.server_name
    server_backups_dir.mkdir(parents=True)
    await app_context.settings.set("paths.backups", str(backups_dir))

    response = admin_auth_client.post(
        f"/api/server/{real_bedrock_server.server_name}/restore/action",
        json={"restore_type": "world", "backup_file": "missing.zip"},
    )
    assert response.status_code == 404
    assert "not found" in response.json()["error"]["message"].lower()


@pytest.mark.parametrize(
    "backup_type, model_name, target",
    [
        ("world", "BackupWorldRequest", "backup_world"),
        ("config", "BackupConfigFileRequest", "backup_config_file"),
        ("all", "BackupAllRequest", "backup_all"),
    ],
)
def test_backup_submits_typed_request(
    admin_auth_client, app_context, real_bedrock_server, backup_type, model_name, target
):
    from bedrock_server_manager.api import backup_restore, models

    with patch(
        "bedrock_server_manager.web.tasks.TaskManager.run_task",
        return_value="typed-backup",
    ) as submit:
        response = admin_auth_client.post(
            f"/api/server/{real_bedrock_server.server_name}/backup/action",
            json={"backup_type": backup_type, "file_to_backup": " server.properties "},
        )
    assert response.status_code == 202
    assert submit.await_args.args == (getattr(backup_restore, target),)
    assert set(submit.await_args.kwargs) == {"request", "app_context", "username"}
    request = submit.await_args.kwargs["request"]
    assert isinstance(request, getattr(models, model_name))
    assert request.server_name == real_bedrock_server.server_name
    assert submit.await_args.kwargs["app_context"] is app_context
    if backup_type == "config":
        assert request.file_to_backup == "server.properties"


@pytest.mark.parametrize(
    "restore_type, model_name, target",
    [
        ("all", "RestoreAllRequest", "restore_all"),
        ("world", "RestoreWorldRequest", "restore_world"),
        ("properties", "RestoreConfigFileRequest", "restore_config_file"),
        ("allowlist", "RestoreConfigFileRequest", "restore_config_file"),
        ("permissions", "RestoreConfigFileRequest", "restore_config_file"),
    ],
)
async def test_restore_submits_typed_request(
    admin_auth_client,
    app_context,
    real_bedrock_server,
    tmp_path,
    restore_type,
    model_name,
    target,
):
    from bedrock_server_manager.api import backup_restore, models

    backup_dir = tmp_path / "backups" / real_bedrock_server.server_name
    backup_dir.mkdir(parents=True)
    backup = backup_dir / "backup.zip"
    backup.touch()
    await app_context.settings.set("paths.backups", str(backup_dir.parent))
    with patch(
        "bedrock_server_manager.web.tasks.TaskManager.run_task",
        return_value="typed-restore",
    ) as submit:
        response = admin_auth_client.post(
            f"/api/server/{real_bedrock_server.server_name}/restore/action",
            json={"restore_type": restore_type, "backup_file": backup.name},
        )
    assert response.status_code == 202
    assert submit.await_args.args == (getattr(backup_restore, target),)
    assert set(submit.await_args.kwargs) == {"request", "app_context", "username"}
    request = submit.await_args.kwargs["request"]
    assert isinstance(request, getattr(models, model_name))
    assert request.server_name == real_bedrock_server.server_name
    assert request.stop_start_server is True
    if restore_type != "all":
        assert request.backup_file_path == str(backup)


@pytest.mark.parametrize(
    "action, kind",
    [
        ("backup", "world"),
        ("backup", "config"),
        ("backup", "all"),
        ("restore", "world"),
        ("restore", "properties"),
        ("restore", "allowlist"),
        ("restore", "permissions"),
        ("restore", "all"),
    ],
)
async def test_backup_restore_tasks_execute_valid_contracts(
    app_context, real_bedrock_server, test_user, tmp_path, action, kind
):
    import asyncio

    from bedrock_server_manager.web.routers.backup_restore import (
        post_backup_action,
        post_restore_action,
    )
    from bedrock_server_manager.web.schemas import (
        BackupActionPayload,
        RestoreActionPayload,
    )

    backup_dir = tmp_path / "backups" / real_bedrock_server.server_name
    backup_dir.mkdir(parents=True)
    (backup_dir / "backup.zip").touch()
    await app_context.settings.set("paths.backups", str(backup_dir.parent))
    # Execute the real decorated API in the real task manager. A busy server
    # skips disk/process work while still exercising request binding and results.
    with patch.object(
        real_bedrock_server.operation_lock, "acquire", side_effect=asyncio.TimeoutError
    ):
        if action == "backup":
            response = await post_backup_action(
                server_name=real_bedrock_server.server_name,
                payload=BackupActionPayload(
                    backup_type=kind, file_to_backup="server.properties"
                ),
                current_user=test_user,
                app_context=app_context,
            )
        else:
            response = await post_restore_action(
                server_name=real_bedrock_server.server_name,
                payload=RestoreActionPayload(
                    restore_type=kind, backup_file="backup.zip"
                ),
                current_user=test_user,
                app_context=app_context,
            )
        await app_context.task_manager.shutdown()
    snapshot = await app_context.task_manager.get_task(response.task_id)
    assert snapshot.status == "completed"
    assert snapshot.result["status"] == "skipped"
    assert snapshot.error is None
