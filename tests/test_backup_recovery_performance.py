"""Recovery safety boundaries and regression tests for sequential archive work."""

import asyncio
import hashlib
import io
import os
import tarfile
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bedrock_server_manager.backups import archive, assurance, recovery
from bedrock_server_manager.backups.models import COMPONENTS
from bedrock_server_manager.error import BackupRestoreError
from bedrock_server_manager.utils.progress import progress_scope


@pytest.mark.parametrize(
    "limit", ["max_files", "max_expanded_bytes", "max_archive_bytes"]
)
async def test_unreadable_capture_never_replaces_previous_recovery_point(
    populated_server, limit
):
    server = populated_server
    await server.settings.set("retention.backups", 1)
    previous = await server.backups.create_snapshot(mode="world")
    await server.settings.set("backups." + limit, 1)
    with pytest.raises(BackupRestoreError, match="limits"):
        await server.backups.create_snapshot(mode="world")
    assert server.backups.resolve_backup(previous.backup_id).exists()
    assert len(list(Path(server.backups._directory()).glob("*.bsmbackup"))) == 1


async def test_reader_limits_count_manifest_and_directories(populated_server):
    backup = await populated_server.backups.create_snapshot(mode="world")
    requirements = archive.manifest_requirements(backup.manifest)
    archive.check_manifest_limits(
        backup.manifest, requirements["expanded_bytes"], requirements["entries"]
    )
    with pytest.raises(BackupRestoreError):
        archive.check_manifest_limits(
            backup.manifest, requirements["expanded_bytes"], requirements["entries"] - 1
        )


@pytest.mark.parametrize("internal", [".bsm-restore", ".BSM-restore", ".BsM-capture"])
async def test_internal_paths_are_reserved_case_insensitively(
    populated_server, internal
):
    backup = await populated_server.backups.create_snapshot(mode="full")
    manifest = backup.manifest.model_copy(
        update={
            "components": {
                name: "included" if name == "server_directory" else "absent"
                for name in COMPONENTS
            },
            "files": [],
            "directories": ["server-directory", "server-directory/" + internal],
        }
    )
    with pytest.raises(ValueError, match="Reserved"):
        archive.validate_manifest(manifest)
    root = Path(populated_server.paths.server_dir)
    (root / internal).mkdir(exist_ok=True)
    from bedrock_server_manager.backups.selection import server_entries

    assert root / internal not in server_entries(root)


async def test_inspection_does_not_materialize_contained_files(
    populated_server, monkeypatch
):
    backup = await populated_server.backups.create_snapshot(mode="world")
    original_open = Path.open

    def guarded(path, *args, **kwargs):
        if ".bsm-inspect-" in str(path) and path.name != ".payload":
            pytest.fail("Inspection materialized a contained file")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)
    assert (
        await populated_server.backups.inspect_snapshot(backup.backup_id)
    ).manifest.files


async def test_extract_hashes_without_reopening_files(populated_server, monkeypatch):
    backup = await populated_server.backups.create_snapshot(mode="world")

    def unexpected(*args, **kwargs):
        pytest.fail("Extraction reopened a file for hashing")

    monkeypatch.setattr(archive, "digest", unexpected)
    assert (
        await populated_server.backups.verify_snapshot(backup.backup_id)
    ).status == "verified"


async def test_drill_uses_one_extraction_and_reports_stages(
    populated_server, monkeypatch
):
    backup = await populated_server.backups.create_snapshot(mode="world")
    original = populated_server.backups.unpack_snapshot
    count = 0

    def counted(*args, cancellation_event=None, stage_callback=None, **kwargs):
        nonlocal count
        count += 1
        return original(
            *args,
            cancellation_event=cancellation_event,
            stage_callback=stage_callback,
            **kwargs,
        )

    monkeypatch.setattr(populated_server.backups, "unpack_snapshot", counted)
    stages = []

    async def stage(message):
        stages.append(message)

    async with asyncio.timeout(10):
        with progress_scope(stage):
            result = await assurance.recovery_drill(
                populated_server.backups, backup.backup_id
            )
    assert count == 1 and result["status"] == "passed"
    assert "Authenticating backup payload" in stages
    assert "Extracting and hashing backup contents" in stages
    assert "Testing isolated restore extraction" in stages


async def test_changed_archive_invalidates_passed_drill(populated_server):
    backup = await populated_server.backups.create_snapshot(mode="world")
    await assurance.recovery_drill(populated_server.backups, backup.backup_id)
    path = populated_server.backups.resolve_backup(backup.backup_id)
    metadata = path.stat()
    os.utime(path, ns=(metadata.st_atime_ns, metadata.st_mtime_ns + 1000000000))
    assert (await populated_server.backups.list_snapshots())[0].drill is None
    assert (await populated_server.backups.backup_health()).drill is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("verification", {"status": "not-a-status"}),
        ("copies", {"offsite": {"status": "failed", "next_retry_at": "bad-date"}}),
        ("read_requirements", {"entries": "not-an-integer"}),
    ],
)
async def test_bad_metadata_is_preserved_and_cannot_break_capture(
    populated_server, field, value
):
    backups = populated_server.backups
    previous = await backups.create_snapshot(mode="world")
    value_to_save = value
    value = backups.catalog.load()
    value["archives"][previous.backup_id][field] = value_to_save
    backups.catalog.save(value)
    newest = await backups.create_snapshot(mode="world")
    value = backups.catalog.load()
    assert previous.backup_id in value["invalid_archives"]
    records = {item.backup_id: item for item in await backups.list_snapshots()}
    assert records[previous.backup_id].pinned
    assert records[previous.backup_id].error
    assert newest.backup_id in records


async def test_missing_catalog_timestamp_does_not_fail_retention(populated_server):
    backups = populated_server.backups
    previous = await backups.create_snapshot(mode="world")
    backups.catalog.update(previous.backup_id, created_at=None)
    assert (await backups.create_snapshot(mode="world")).error is None


async def test_lowered_limits_block_retention_using_unreadable_replacement(
    populated_server,
):
    server = populated_server
    await server.settings.set("retention.backups", 0)
    first = await server.backups.create_snapshot(mode="world")
    second = await server.backups.create_snapshot(mode="world")
    await server.settings.set("backups.max_files", 1)
    await server.settings.set("retention.backups", 1)
    await server.backups.prune_snapshots()
    assert server.backups.resolve_backup(first.backup_id).exists()
    assert server.backups.resolve_backup(second.backup_id).exists()


async def test_read_only_operations_do_not_queue_behind_recovery(populated_server):
    from bedrock_server_manager.backups.reports import recovery_report
    from bedrock_server_manager.web.routers.backup_restore import download_snapshot

    backup = await populated_server.backups.create_snapshot(mode="world")
    entered, release = asyncio.Event(), asyncio.Event()

    async def holder():
        async with populated_server.operation_lock:
            entered.set()
            await release.wait()

    task = asyncio.create_task(holder())
    await entered.wait()
    try:
        async with asyncio.timeout(2):
            await populated_server.backups.list_backups("all")
            await recovery_report(populated_server.backups)
            response = await download_snapshot(
                backup.backup_id,
                populated_server.server_name,
                SimpleNamespace(username="admin"),
                SimpleNamespace(get_server=lambda *args, **kwargs: populated_server),
            )
            assert b"".join([chunk async for chunk in response.body_iterator])
    finally:
        release.set()
        await task


@pytest.mark.skipif(os.name == "nt", reason="POSIX directory durability")
def test_rollback_flushes_target_parent_before_completion(tmp_path, monkeypatch):
    root = tmp_path / "server"
    root.mkdir()
    (root / "server.properties").write_text("old")
    server = SimpleNamespace(
        paths=SimpleNamespace(server_dir=str(root)), server_name="test"
    )
    journal = recovery.RestoreJournal(server)
    journal.begin(["server.properties"], False)
    replacement = root / "replacement"
    replacement.write_text("new")
    journal.replace(0, replacement)
    original_open, original_fsync = os.open, os.fsync
    original_json = recovery.atomic_json
    descriptors, flushed = {}, set()

    def opened(path, *args, **kwargs):
        descriptor = original_open(path, *args, **kwargs)
        descriptors[descriptor] = Path(path)
        return descriptor

    def flush(descriptor):
        flushed.add(descriptors.get(descriptor))
        return original_fsync(descriptor)

    def record(path, value):
        if value["entries"][0]["rolled_back"]:
            assert root in flushed and journal.path in flushed
        return original_json(path, value)

    monkeypatch.setattr(os, "open", opened)
    monkeypatch.setattr(os, "fsync", flush)
    monkeypatch.setattr(recovery, "atomic_json", record)
    journal._rollback_files(journal._load())
    assert (root / "server.properties").read_text() == "old"


@pytest.mark.parametrize("operation", ["token", "comparison", "tree", "flush"])
async def test_prepare_workers_cooperate_with_cancellation(populated_server, operation):
    backup = await populated_server.backups.create_snapshot(mode="world")
    event = threading.Event()
    event.set()
    server = populated_server.backups
    root = Path(populated_server.paths.server_dir)
    with pytest.raises(InterruptedError):
        if operation == "token":
            server._plan_token(server.resolve_backup(backup.backup_id), {}, event)
        elif operation == "comparison":
            server.restore_comparison(root, {"world": "worlds/test"}, event)
        elif operation == "tree":
            server._check_tree(root, event)
        else:
            recovery.sync_tree(root, event)


async def test_retention_failure_reports_created_archive(populated_server, monkeypatch):
    monkeypatch.setattr(
        populated_server.backups,
        "prune_snapshots",
        AsyncMock(side_effect=OSError("maintenance failure")),
    )
    result = await populated_server.backups.create_snapshot(mode="world")
    assert result.error and "Retention" in result.error
    assert populated_server.backups.resolve_backup(result.backup_id).exists()


@pytest.mark.parametrize("reverse", [False, True])
async def test_conflicting_file_parents_are_rejected(
    populated_server, tmp_path, reverse
):
    from bedrock_server_manager.backups.models import BackupFile

    original = await populated_server.backups.create_snapshot(mode="world")
    files = [
        BackupFile(
            path=name,
            component="world",
            size=1,
            sha256=hashlib.sha256(content).hexdigest(),
        )
        for name, content in [("world/a", b"a"), ("world/a/b", b"b")]
    ]
    manifest = original.manifest.model_copy(
        update={"files": files, "directories": ["world"]}
    )
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as payload:
        archive.add_json(payload, "manifest.json", manifest.model_dump(mode="json"))
        directory = tarfile.TarInfo("world")
        directory.type = tarfile.DIRTYPE
        payload.addfile(directory)
        for item in reversed(files) if reverse else files:
            info = tarfile.TarInfo(item.path)
            info.size = 1
            payload.addfile(info, io.BytesIO(b"a" if item.path == "world/a" else b"b"))
    path = tmp_path / "conflict.bsmbackup"
    with tarfile.open(path, "w:") as outer:
        archive.add_json(
            outer,
            "bsm.json",
            {
                "format": "bsmbackup",
                "container_version": 1,
                "encrypted": False,
                "key_id": None,
            },
        )
        info = tarfile.TarInfo("payload.tar.gz")
        info.size = len(buffer.getvalue())
        outer.addfile(info, io.BytesIO(buffer.getvalue()))
    with pytest.raises(BackupRestoreError):
        archive.unpack(path, tmp_path / "extracted")


async def test_download_cancellation_closes_worker_owned_handle(
    populated_server, monkeypatch
):
    from bedrock_server_manager.web.routers.backup_restore import download_snapshot

    backup = await populated_server.backups.create_snapshot(mode="world")
    path = populated_server.backups.resolve_backup(backup.backup_id)
    entered, release = threading.Event(), threading.Event()
    original = Path.open
    handles = []

    def paused(source, *args, **kwargs):
        stream = original(source, *args, **kwargs)
        if source == path:
            handles.append(stream)
            entered.set()
            assert release.wait(5)
        return stream

    monkeypatch.setattr(Path, "open", paused)
    task = asyncio.create_task(
        download_snapshot(
            backup.backup_id,
            populated_server.server_name,
            SimpleNamespace(username="admin"),
            SimpleNamespace(get_server=lambda *args, **kwargs: populated_server),
        )
    )
    try:
        assert await asyncio.to_thread(entered.wait, 3)
        task.cancel()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
    finally:
        release.set()
        if not task.done():
            await task
    assert handles and handles[0].closed


async def test_durable_extraction_syncs_existing_write_handles(
    populated_server, tmp_path, monkeypatch
):
    backup = await populated_server.backups.create_snapshot(mode="world")
    destination = tmp_path / "durable"
    original_open = Path.open
    original_sync = os.fsync
    handles = {}
    synced = set()

    def opened(path, mode="r", *args, **kwargs):
        if path.is_relative_to(destination) and path.name != ".payload":
            assert mode == "wb", "Durability must not reopen extracted files"
        handle = original_open(path, mode, *args, **kwargs)
        if (
            path.is_relative_to(destination)
            and mode == "wb"
            and path.name != ".payload"
        ):
            handles[handle.fileno()] = handle
        return handle

    def synced_handle(fd):
        if fd in handles:
            assert not handles[fd].closed
            assert handles[fd].writable()
            synced.add(handles[fd].name)
        return original_sync(fd)

    monkeypatch.setattr(Path, "open", opened)
    monkeypatch.setattr(os, "fsync", synced_handle)
    populated_server.backups.unpack_snapshot(
        populated_server.backups.resolve_backup(backup.backup_id),
        destination,
        None,
        durable=True,
    )
    assert synced == {str(destination / item.path) for item in backup.manifest.files}


async def test_drill_extracts_on_destination_without_copy_pass(
    populated_server, monkeypatch
):
    from bedrock_server_manager.backups import server as implementation

    backup = await populated_server.backups.create_snapshot(mode="world")
    original = populated_server.backups.unpack_snapshot
    original_verify = implementation.verify_copy
    checked = []

    def extracted(path, destination, *args, **kwargs):
        assert destination.parent == Path(populated_server.paths.server_dir)
        assert kwargs["durable"] is True
        return original(path, destination, *args, **kwargs)

    def verified(destination, *args, **kwargs):
        checked.append(destination)
        return original_verify(destination, *args, **kwargs)

    def unexpected(*args, **kwargs):
        pytest.fail("Drill performed a second copy pass")

    monkeypatch.setattr(populated_server.backups, "unpack_snapshot", extracted)
    monkeypatch.setattr(implementation, "copy_source", unexpected)
    monkeypatch.setattr(implementation, "verify_copy", verified)
    await assurance.recovery_drill(populated_server.backups, backup.backup_id)
    assert len(checked) == 1
    assert not checked[0].exists()


async def test_failed_durable_extraction_does_not_stop_or_replace_server(
    populated_server, monkeypatch
):
    server = populated_server
    snapshot = await server.backups.create_snapshot(mode="world")
    plan = await server.backups.plan_restore(snapshot.backup_id, ["world"])
    live = next((Path(server.paths.server_dir) / "worlds").rglob("level.dat"))
    before = live.read_bytes()
    stop = AsyncMock()

    def failed_sync(fd):
        raise OSError("Simulated flush failure")

    monkeypatch.setattr(os, "fsync", failed_sync)
    with pytest.raises(BackupRestoreError, match="Backup validation failed"):
        await server.backups.restore_snapshot(
            snapshot.backup_id, plan.components, plan.token, stop_server=stop
        )
    stop.assert_not_awaited()
    assert live.read_bytes() == before
    assert not list(Path(server.paths.server_dir).glob(".bsm-restore-stage-*"))
