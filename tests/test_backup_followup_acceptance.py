"""Disposable runtime/filesystem restore acceptance and bounded work telemetry."""

import asyncio
from pathlib import Path

import pytest

from bedrock_server_manager.api.backup_restore import restore_server_snapshot
from bedrock_server_manager.api.models.backup_restore import RestoreSnapshotRequest
from bedrock_server_manager.backups import recovery
from bedrock_server_manager.backups.models import ServerSettingsExport
from bedrock_server_manager.backups.recovery import apply_settings
from bedrock_server_manager.backups.server import copy_source
from bedrock_server_manager.backups.work import backup_worker
from bedrock_server_manager.utils.progress import progress_scope


async def test_disposable_server_restores_world_settings_safety_and_restart(
    populated_server, app_context
):
    server = populated_server
    root = Path(server.paths.server_dir)
    world = root / "worlds" / await server.get_world_name()
    original = (world / "level.dat").read_bytes()
    await apply_settings(
        server,
        ServerSettingsExport(
            autostart=False,
            autoupdate=True,
            target_version="LATEST",
            custom={"acceptance": "original"},
        ),
    )
    server.backups.credentials.rotate()
    backup = await server.backups.create_snapshot(
        encrypted=True, components=["world", "bsm_settings"]
    )
    (world / "level.dat").write_bytes(b"before-restore")
    await apply_settings(
        server,
        ServerSettingsExport(
            autostart=False,
            autoupdate=False,
            target_version="LATEST",
            custom={"acceptance": "changed"},
        ),
    )
    (root / "permissions.json").write_text(
        '[{"xuid":"unchanged","permission":"member"}]'
    )
    unselected = (root / "permissions.json").read_bytes()
    plan = await server.backups.plan_restore(
        backup.backup_id, ["world", "bsm_settings"]
    )
    await server.start()
    old_child = server.process._process
    assert old_child is not None and old_child.returncode is None
    try:
        result = await restore_server_snapshot(
            RestoreSnapshotRequest(
                server_name=server.server_name,
                backup_id=backup.backup_id,
                components=plan.components,
                token=plan.token,
                stop_running=True,
                restart=True,
            ),
            app_context=app_context,
        )
        assert result.result.committed and result.result.restarted
        assert old_child.returncode is not None
        assert server.process._process is not old_child
        assert await server.is_running()
        assert (world / "level.dat").read_bytes() == original
        assert server.configuration.snapshot().custom == {"acceptance": "original"}
        assert server.configuration.snapshot().autoupdate
        assert (root / "permissions.json").read_bytes() == unselected
        safety = await server.backups.inspect_snapshot(result.result.safety_backup_id)
        assert safety.manifest.reason == "pre_restore"
        assert not recovery.RestoreJournal(server).path.exists()
    finally:
        await server.stop()


async def test_interrupted_restore_returns_current_world_and_settings(
    populated_server, monkeypatch
):
    server = populated_server
    world = Path(server.paths.server_dir) / "worlds" / await server.get_world_name()
    backup = await server.backups.create_snapshot(components=["world", "bsm_settings"])
    (world / "level.dat").write_bytes(b"current-world")
    await apply_settings(
        server,
        ServerSettingsExport(
            autostart=False,
            autoupdate=False,
            target_version="LATEST",
            custom={"acceptance": "current"},
        ),
    )
    plan = await server.backups.plan_restore(
        backup.backup_id, ["world", "bsm_settings"]
    )
    original = recovery.RestoreJournal.replace

    def interrupted(journal, index, source):
        original(journal, index, source)
        raise asyncio.CancelledError

    monkeypatch.setattr(recovery.RestoreJournal, "replace", interrupted)
    with pytest.raises(asyncio.CancelledError):
        await server.backups.restore_snapshot(
            backup.backup_id, plan.components, plan.token
        )
    assert (world / "level.dat").read_bytes() == b"current-world"
    assert server.configuration.snapshot().custom == {"acceptance": "current"}
    assert not recovery.RestoreJournal(server).path.exists()
    assert any(
        item.purpose == "pre_restore" for item in await server.backups.list_snapshots()
    )


async def test_copy_and_flush_report_counts_and_separate_fsync_time(tmp_path, caplog):
    source = tmp_path / "source"
    source.mkdir()
    (source / "first").write_bytes(b"abc")
    (source / "second").write_bytes(b"defgh")
    target = tmp_path / "copy"
    caplog.set_level("DEBUG")
    stages = []

    async def stage(message):
        stages.append(message)

    with progress_scope(stage):
        await backup_worker(copy_source, source, target)
        await backup_worker(recovery.sync_tree, target)
    assert (target / "first").read_bytes() == b"abc"
    assert any("Copying backup files (2 files; 8 bytes)" == item for item in stages)
    assert any("Flushing restore files (2 files; 8 bytes)" == item for item in stages)
    records = [
        r.message for r in caplog.records if r.message.startswith("Backup file work:")
    ]
    assert len(records) == 2
    assert "source_open_ms=" in records[0] and "target_open_ms=" in records[0]
    assert "read_ms=" in records[0] and "permissions_ms=" in records[0]
    assert "fsync_ms=" in records[1] and "open_ms=" in records[1]
    assert all("status=completed" in item for item in records)
    assert str(source) not in " ".join(records)


def test_file_progress_is_throttled_between_start_and_completion():
    from bedrock_server_manager.backups.work import FileWork

    stages = []
    work = FileWork("Copying backup files", stages.append)
    moment = 0.0
    work._clock = lambda: moment
    work.last_progress = 0.0
    for moment in (0.1, 0.2, 0.9, 1.0, 1.1, 1.9, 2.0):
        work.files += 1
        work.progress()
    assert len(stages) == 2
    work.progress(force=True)
    assert len(stages) == 3 and "7 files" in stages[-1]
