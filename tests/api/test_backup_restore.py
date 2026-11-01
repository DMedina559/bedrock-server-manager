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


async def test_unified_api_round_trip_alias_and_pruning(app_context, populated_server):
    name = populated_server.server_name

    # Prunes unified archives and legacy backup_all alias uses one archive
    await populated_server.settings.set("retention.backups", 3)
    for _ in range(2):
        await populated_server.backups.create_snapshot()
    alias_res = await backup_all(
        BackupAllRequest(server_name=name),
        app_context=app_context,
    )
    paths = {
        item.path
        for item in alias_res.details.components.values()
        if item.outcome == "completed"
    }
    assert len(paths) == 1 and next(iter(paths)).endswith(".bsmbackup")

    await populated_server.settings.set("retention.backups", 1)
    prune_res = await prune_old_backups(
        PruneOldBackupsRequest(server_name=name), app_context=app_context
    )
    assert prune_res.status == "success"
    snapshots = await populated_server.backups.list_snapshots()
    assert len(snapshots) == 1

    # Round-trip create, list, inspect, plan, restore
    await populated_server.settings.set("retention.backups", 3)
    snapshot = (
        await create_server_backup(
            CreateSnapshotRequest(server_name=name), app_context=app_context
        )
    ).backup
    listing = await list_server_snapshots(
        ListSnapshotsRequest(server_name=name), app_context=app_context
    )
    assert any(b.backup_id == snapshot.backup_id for b in listing.backups)
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
