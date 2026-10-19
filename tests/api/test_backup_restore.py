from pathlib import Path

from bedrock_server_manager.api.backup_restore import (
    backup_all,
    create_server_backup,
    inspect_server_backup,
    list_server_snapshots,
    plan_server_restore,
    prune_old_backups,
    restore_server_snapshot,
)
from bedrock_server_manager.api.models import BackupAllRequest, PruneOldBackupsRequest
from bedrock_server_manager.api.models.backup_restore import (
    CreateSnapshotRequest,
    InspectSnapshotRequest,
    ListSnapshotsRequest,
    PlanSnapshotRestoreRequest,
    RestoreSnapshotRequest,
)


async def test_unified_api_round_trip(app_context, populated_server):
    name = populated_server.server_name
    snapshot = (
        await create_server_backup(
            CreateSnapshotRequest(server_name=name), app_context=app_context
        )
    ).backup
    listing = await list_server_snapshots(
        ListSnapshotsRequest(server_name=name), app_context=app_context
    )
    assert listing.backups[0].backup_id == snapshot.backup_id
    inspection = await inspect_server_backup(
        InspectSnapshotRequest(server_name=name, backup_id=snapshot.backup_id),
        app_context=app_context,
    )
    assert inspection.backup.manifest.source_server == name
    world = (
        Path(populated_server.paths.server_dir)
        / "worlds"
        / await populated_server.get_world_name()
    )
    marker = world / "marker.txt"
    marker.write_text("remove this newer file")
    request = dict(server_name=name, backup_id=snapshot.backup_id, components=["world"])
    plan = (
        await plan_server_restore(
            PlanSnapshotRestoreRequest(**request), app_context=app_context
        )
    ).plan
    result = await restore_server_snapshot(
        RestoreSnapshotRequest(**request, token=plan.token), app_context=app_context
    )
    assert result.result.committed
    assert not marker.exists()


async def test_legacy_backup_all_alias_uses_one_archive(app_context, populated_server):
    result = await backup_all(
        BackupAllRequest(server_name=populated_server.server_name),
        app_context=app_context,
    )
    paths = {
        item.path
        for item in result.details.components.values()
        if item.outcome == "completed"
    }
    assert len(paths) == 1
    assert next(iter(paths)).endswith(".bsmbackup")


async def test_api_prunes_unified_archives(app_context, populated_server):
    server = populated_server
    await server.settings.set("retention.backups", 3)
    for _ in range(3):
        await server.backups.create_snapshot()
    await server.settings.set("retention.backups", 1)
    result = await prune_old_backups(
        PruneOldBackupsRequest(server_name=server.server_name), app_context=app_context
    )
    assert result.status == "success"
    snapshots = await server.backups.list_snapshots()
    assert len(snapshots) == 1


async def test_restore_running_server_skips_start_backup_and_update(
    app_context, populated_server, plugin_factory
):

    server = populated_server
    await server.set_autoupdate(True)
    snapshot = await server.backups.create_snapshot()
    await server.start()
    original_process = server.process._process
    for name in ("backup_on_start", "update_before_start"):
        path = (
            Path(__file__).parents[2]
            / "src/bedrock_server_manager/plugins/default"
            / f"{name}.py"
        )
        await plugin_factory(name, path.read_text())
    selected = ["world", "bsm_settings"]
    plan = await server.backups.plan_restore(snapshot.backup_id, selected)
    result = await restore_server_snapshot(
        RestoreSnapshotRequest(
            server_name=server.server_name,
            backup_id=snapshot.backup_id,
            components=selected,
            token=plan.token,
        ),
        app_context=app_context,
    )
    assert result.result.restarted
    assert result.result.restart_error is None
    assert original_process.returncode is not None
    snapshots = await server.backups.list_snapshots()
    assert len(snapshots) == 2
    assert sum(item.purpose == "pre_restore" for item in snapshots) == 1
    assert server.configuration.snapshot().autoupdate
