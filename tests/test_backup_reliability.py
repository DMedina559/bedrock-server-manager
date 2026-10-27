"""Recover real process interruptions and validate backup scheduling boundaries."""

import asyncio
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bedrock_server_manager.backups.models import BASE_COMPONENTS, PACK_COMPONENTS
from bedrock_server_manager.backups.recovery import RestoreJournal
from bedrock_server_manager.backups.schedule import occurrences, run_due
from bedrock_server_manager.state.settings import BackupSchedule


@pytest.mark.parametrize("stage", ["begin", "first_file", "all_files", "commit"])
async def test_process_killed_during_restore_is_recovered(tmp_path, stage):
    root = tmp_path / "server"
    root.mkdir()
    (root / "server.properties").write_text("original")
    (root / "behavior_packs").mkdir()
    (root / "behavior_packs" / "pack.json").write_text("original pack")
    script = """
import sys
from pathlib import Path
from types import SimpleNamespace
from bedrock_server_manager.backups.recovery import RestoreJournal
root = Path(sys.argv[1])
server = SimpleNamespace(paths=SimpleNamespace(server_dir=str(root)), server_name="test")
journal = RestoreJournal(server)
journal.begin(["server.properties", "behavior_packs"], False)
stage = sys.argv[2]
if stage != "begin":
    replacement = root / "replacement"
    replacement.write_text("replacement")
    journal.replace(0, replacement)
if stage in ("all_files", "commit"):
    replacement = root / "replacement-pack"
    replacement.mkdir()
    (replacement / "pack.json").write_text("replacement pack")
    journal.replace(1, replacement)
if stage == "commit":
    journal.commit()
print("ready", flush=True)
sys.stdin.read()
"""
    process = subprocess.Popen(
        [sys.executable, "-c", script, str(root), stage],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        ready = await asyncio.wait_for(
            asyncio.to_thread(process.stdout.readline), timeout=20
        )
        if ready != "ready\n":
            raise AssertionError(process.stderr.read())
        process.kill()
        await asyncio.to_thread(process.wait, 10)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=10)
        for stream in (process.stdin, process.stdout, process.stderr):
            stream.close()
    server = SimpleNamespace(
        paths=SimpleNamespace(server_dir=str(root)),
        server_name="test",
        is_running=AsyncMock(return_value=False),
    )
    # A new recovery owner sees only persisted state from the terminated process.
    await RestoreJournal(server).recover()
    assert (root / "server.properties").read_text() == (
        "replacement" if stage == "commit" else "original"
    )
    assert (root / "behavior_packs" / "pack.json").read_text() == (
        "replacement pack" if stage == "commit" else "original pack"
    )
    assert not (root / ".bsm-restore").exists()
    await RestoreJournal(server).recover()


async def test_pack_capture_dry_run_and_restore(populated_server):
    server = populated_server
    root = Path(server.paths.server_dir)
    for name in PACK_COMPONENTS:
        (root / name).mkdir(exist_ok=True)
        (root / name / "manifest.json").write_text('{"pack":"original"}')
    snapshot = await server.backups.create_snapshot(
        components=list(BASE_COMPONENTS + PACK_COMPONENTS)
    )
    assert snapshot.manifest.format_version == 1
    assert all(
        snapshot.manifest.components[name] == "included" for name in PACK_COMPONENTS
    )
    for name in PACK_COMPONENTS:
        (root / name / "manifest.json").write_text('{"pack":"changed"}')
    plan = await server.backups.plan_restore(
        snapshot.backup_id, list(PACK_COMPONENTS), dry_run=True
    )
    assert plan.dry_run and plan.checked_files == 4 and plan.sufficient_space
    assert all(
        (root / name / "manifest.json").read_text() == '{"pack":"changed"}'
        for name in PACK_COMPONENTS
    )
    await server.backups.restore_snapshot(
        snapshot.backup_id, plan.components, plan.token
    )
    assert all(
        (root / name / "manifest.json").read_text() == '{"pack":"original"}'
        for name in PACK_COMPONENTS
    )


async def test_old_manifests_remain_readable(populated_server, tmp_path):
    from bedrock_server_manager.backups.archive import unpack, write_archive
    from bedrock_server_manager.backups.models import BASE_COMPONENTS, PREFIXES

    server = populated_server
    snapshot = await server.backups.create_snapshot()
    staging = tmp_path / "contents"
    staging.mkdir()
    manifest = unpack(server.backups.resolve_backup(snapshot.backup_id), staging)
    old = manifest.model_copy(
        update={
            "format_version": 1,
            "files": [
                item for item in manifest.files if item.component in BASE_COMPONENTS
            ],
            "directories": [
                name
                for name in manifest.directories
                if any(
                    name == PREFIXES[c] or name.startswith(PREFIXES[c] + "/")
                    for c in BASE_COMPONENTS
                )
            ],
            "components": {key: manifest.components[key] for key in BASE_COMPONENTS},
        }
    )
    target = tmp_path / "old.bsmbackup"
    write_archive(staging, target, old, None, None)
    destination = tmp_path / "read-old"
    destination.mkdir()
    assert unpack(target, destination).format_version == 1


async def test_schedules_catch_up_once_and_survive_restart(populated_server):
    backups = populated_server.backups
    name = populated_server.server_name
    await populated_server.settings.set(
        "backups.schedules",
        {name: {"time": "03:00", "timezone": "UTC", "stagger_minutes": 0}},
    )
    activated = datetime(2026, 10, 19, 2, tzinfo=timezone.utc)
    assert not await run_due(backups, activated)
    assert await run_due(backups, activated + timedelta(hours=3))
    assert not await run_due(backups, activated + timedelta(hours=4))
    summaries = await backups.list_snapshots()
    assert len(summaries) == 1 and summaries[0].purpose == "scheduled"
    record = backups.catalog.load()
    record["schedule"][
        "status"
    ] = "running"  # Publication preceded a manager interruption.
    backups.catalog.save(record)
    assert await run_due(backups, activated + timedelta(hours=5))
    assert len(await backups.list_snapshots()) == 1


@pytest.mark.parametrize("day", [(2026, 3, 8), (2026, 11, 1)])
def test_schedule_dst_has_one_occurrence_per_local_day(day):
    config = BackupSchedule(
        time="02:30", timezone="America/Los_Angeles", stagger_minutes=0
    ).model_dump()
    moment = datetime(*day, 12, tzinfo=timezone.utc)
    slots = occurrences(config, "test", moment)
    assert len(slots) == len(set(slots))
    assert all((b - a).total_seconds() > 0 for a, b in zip(slots, slots[1:]))


async def test_metadata_edits_do_not_rewrite_archive(populated_server):
    from bedrock_server_manager.backups.archive import digest

    backups = populated_server.backups
    snapshot = await backups.create_snapshot()
    before = digest(backups.resolve_backup(snapshot.backup_id))
    await backups.annotate_snapshot(
        snapshot.backup_id, "Before upgrade", "Recovery checkpoint"
    )
    item = (await backups.list_snapshots())[0]
    assert item.label == "Before upgrade" and item.notes == "Recovery checkpoint"
    assert digest(backups.resolve_backup(snapshot.backup_id)) == before


async def test_capacity_reports_both_filesystems_and_blocks_before_stop(
    populated_server, monkeypatch
):
    from bedrock_server_manager.backups import space
    from bedrock_server_manager.error import BackupRestoreError

    server = populated_server
    snapshot = await server.backups.create_snapshot()
    server_root = Path(server.paths.server_dir)

    class Anchor:
        def __init__(self, device):
            self.device = device

        def stat(self):
            return SimpleNamespace(st_dev=self.device)

    monkeypatch.setattr(
        space, "existing_parent", lambda path: Anchor(1 if path == server_root else 2)
    )
    monkeypatch.setattr(
        space.shutil,
        "disk_usage",
        lambda path: SimpleNamespace(free=0 if path.device == 2 else 10**12),
    )
    plan = await server.backups.plan_restore(snapshot.backup_id, ["server.properties"])
    assert len(plan.volumes) == 2 and not plan.sufficient_space
    assert next(v for v in plan.volumes if "backups" in v.roles).sufficient is False
    stop = AsyncMock()
    with pytest.raises(BackupRestoreError, match="Insufficient space"):
        await server.backups.restore_snapshot(
            snapshot.backup_id, plan.components, plan.token, stop_server=stop
        )
    stop.assert_not_called()


async def test_maintenance_yields_to_interactive_work(populated_server, monkeypatch):
    backups = populated_server.backups
    await backups.create_snapshot()
    verify = AsyncMock()
    monkeypatch.setattr(backups, "verify_snapshot", verify)
    async with populated_server.operation_lock:
        await backups.maintain_backups()
    verify.assert_not_called()


async def test_scheduled_failures_have_bounded_retries(populated_server, monkeypatch):
    backups = populated_server.backups
    name = populated_server.server_name
    await populated_server.settings.set(
        "backups.schedules",
        {
            name: {
                "time": "03:00",
                "timezone": "UTC",
                "stagger_minutes": 0,
                "catch_up": False,
            }
        },
    )
    activated = datetime(2026, 10, 19, 2, tzinfo=timezone.utc)
    await run_due(backups, activated)
    create = AsyncMock(side_effect=OSError("Disk unavailable"))
    monkeypatch.setattr(backups, "create_snapshot", create)
    for minutes in (0, 10, 30, 90, 180):
        await run_due(backups, activated + timedelta(hours=1, minutes=minutes))
    assert create.await_count == 3
    assert backups.catalog.load()["schedule"]["status"] == "failed"


async def test_scheduled_capture_uses_backup_hooks(app_context, populated_server):
    from bedrock_server_manager.api.backup_restore import create_server_backup
    from bedrock_server_manager.api.models.backup_restore import CreateSnapshotRequest

    name = populated_server.server_name
    await populated_server.settings.set(
        "backups.schedules",
        {name: {"time": "03:00", "timezone": "UTC", "stagger_minutes": 0}},
    )
    seen = []

    async def before(**data):
        seen.append(data["request"].purpose)

    app_context.events.subscribe("before_backup", before, owner="application")

    async def capture(slot):
        await create_server_backup(
            CreateSnapshotRequest(
                server_name=name, purpose="scheduled", schedule_slot=slot
            ),
            app_context=app_context,
        )

    activated = datetime(2026, 10, 19, 2, tzinfo=timezone.utc)
    await run_due(populated_server.backups, activated, capture=capture)
    await run_due(
        populated_server.backups, activated + timedelta(hours=1), capture=capture
    )
    assert seen == ["scheduled"]
