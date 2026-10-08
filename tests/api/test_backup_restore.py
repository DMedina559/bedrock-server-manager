from pathlib import Path

from bedrock_server_manager.api.backup_restore import (
    backup_all,
    backup_config_file,
    backup_world,
    list_backup_files,
    prune_old_backups,
    restore_all,
    restore_config_file,
    restore_world,
)
from bedrock_server_manager.api.models import (
    BackupAllRequest,
    BackupConfigFileRequest,
    BackupWorldRequest,
    ListBackupFilesRequest,
    PruneOldBackupsRequest,
    RestoreAllRequest,
    RestoreConfigFileRequest,
    RestoreWorldRequest,
)


async def test_config_backup_and_restore_round_trip(app_context, populated_server):
    name = populated_server.server_name
    properties = Path(populated_server.server_dir) / "server.properties"
    original = properties.read_bytes()
    assert (
        await backup_config_file(
            BackupConfigFileRequest(
                server_name=name, file_to_backup="server.properties"
            ),
            app_context=app_context,
        )
    ).status == "success"
    files = (
        await list_backup_files(
            ListBackupFilesRequest(server_name=name, backup_type="properties"),
            app_context=app_context,
        )
    ).backups
    assert files
    properties.write_text("server-name=changed\n")
    backup = Path(files[0])
    assert (
        await restore_config_file(
            RestoreConfigFileRequest(server_name=name, backup_file_path=str(backup)),
            app_context=app_context,
        )
    ).status == "success"
    assert properties.read_bytes() == original


async def test_world_backup_and_restore_preserves_world_files(
    app_context, populated_server
):
    name = populated_server.server_name
    world = (
        Path(populated_server.server_dir)
        / "worlds"
        / await populated_server.get_world_name()
    )
    marker = world / "integration.txt"
    marker.write_text("original")
    assert (
        await backup_world(
            BackupWorldRequest(server_name=name), app_context=app_context
        )
    ).status == "success"
    files = (
        await list_backup_files(
            ListBackupFilesRequest(server_name=name, backup_type="world"),
            app_context=app_context,
        )
    ).backups
    marker.write_text("changed")
    backup = Path(files[0])
    assert (
        await restore_world(
            RestoreWorldRequest(server_name=name, backup_file_path=str(backup)),
            app_context=app_context,
        )
    ).status == "success"
    assert marker.read_text() == "original"


async def test_backup_all_and_restore_all_preserve_configuration(
    app_context, populated_server
):
    name = populated_server.server_name
    original = (Path(populated_server.server_dir) / "server.properties").read_bytes()
    assert (
        await backup_all(BackupAllRequest(server_name=name), app_context=app_context)
    ).status == "success"
    (Path(populated_server.server_dir) / "server.properties").write_text("changed")
    assert (
        await restore_all(RestoreAllRequest(server_name=name), app_context=app_context)
    ).status == "success"
    assert (
        Path(populated_server.server_dir) / "server.properties"
    ).read_bytes() == original
    assert (
        await prune_old_backups(
            PruneOldBackupsRequest(server_name=name), app_context=app_context
        )
    ).status == "success"
