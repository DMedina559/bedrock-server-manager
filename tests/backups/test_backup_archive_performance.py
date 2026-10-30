"""Compatibility, permission boundaries, durability, and responsive backup reads."""

import asyncio
import os
import stat
import threading
from types import SimpleNamespace

import pytest

from bedrock_server_manager.backups import server as capture
from bedrock_server_manager.backups.credentials import private_directory


@pytest.mark.parametrize("compression", ["fast", "balanced", "small"])
@pytest.mark.parametrize("encrypted", [False, True])
async def test_compression_profiles_preserve_recovery(
    populated_server, compression, encrypted, caplog
):
    caplog.set_level("DEBUG")
    server = populated_server
    await server.settings.set("backups.compression", compression)
    if encrypted:
        server.backups.credentials.rotate()
    backup = await server.backups.create_snapshot(mode="world", encrypted=encrypted)
    verified = await server.backups.verify_snapshot(backup.backup_id)
    assert verified.status == "verified"
    inspected = await server.backups.inspect_snapshot(backup.backup_id)
    assert inspected.manifest.mode == "world"
    assert inspected.encrypted is encrypted
    assert "Compressing backup" in backup.stage_durations_ms
    assert "Recording archive integrity" in backup.stage_durations_ms
    assert f"purpose=manual compression={compression}" in caplog.text
    messages = [
        record.message
        for record in caplog.records
        if record.message.startswith("Backup payload completed:")
    ]
    assert len(messages) == 1
    message = messages[0]
    level = {"fast": 1, "balanced": 6, "small": 9}[compression]
    assert f"compression={compression} gzip_level={level}" in message
    for metric in (
        "source_open_ms",
        "source_read_ms",
        "source_close_ms",
        "archive_other_ms",
        "total_ms",
        "bytes_read",
    ):
        assert f"{metric}=" in message
    assert "includes tar, gzip, output I/O" in message


async def test_backup_reads_do_not_wait_for_capture(populated_server, monkeypatch):
    server = populated_server
    previous = await server.backups.create_snapshot(mode="world")
    entered, release = threading.Event(), threading.Event()
    original = capture.build_payload

    def paused(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        return original(*args, **kwargs)

    monkeypatch.setattr(capture, "build_payload", paused)
    operation = asyncio.create_task(server.backups.create_snapshot(mode="world"))
    try:
        assert await asyncio.to_thread(entered.wait, 3)
        assert server.operation_lock.locked()
        async with asyncio.timeout(1):
            snapshots = await server.backups.list_snapshots()
            health = await server.backups.backup_health()
        assert [item.backup_id for item in snapshots] == [previous.backup_id]
        assert health.count == 1
    finally:
        release.set()
        await operation


def test_windows_staging_inherits_permissions_without_per_file_acl(
    tmp_path, monkeypatch
):
    staging = private_directory(tmp_path / "private")
    source = tmp_path / "source"
    source.mkdir()
    (source / "nested").mkdir()
    (source / "nested/file").write_text("content")
    monkeypatch.setattr(capture, "os", SimpleNamespace(name="nt"))

    def unexpected_acl(path):
        pytest.fail("Private Windows staging should inherit its directory ACL")

    monkeypatch.setattr(capture, "protect", unexpected_acl)
    capture.copy_source(source, staging / "world", inherited_private=True)
    assert (staging / "world/nested/file").read_text() == "content"


def test_ordinary_copies_still_apply_permissions(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.write_text("content")
    called = []
    monkeypatch.setattr(capture, "protect", called.append)
    target = tmp_path / "target"
    capture.copy_source(source, target)
    assert called == [target]


@pytest.mark.skipif(os.name == "nt", reason="POSIX file mode boundary")
def test_private_staging_keeps_posix_file_modes(tmp_path):
    source = tmp_path / "source"
    source.write_text("content")
    target = private_directory(tmp_path / "private") / "file"
    capture.copy_source(source, target, inherited_private=True)
    assert stat.S_IMODE(target.stat().st_mode) == 0o600


@pytest.mark.skipif(os.name != "nt", reason="Requires native Windows ACL inheritance")
def test_native_windows_private_acl_inheritance(tmp_path):
    import win32security

    staging = private_directory(tmp_path / "private")
    source = tmp_path / "source"
    source.mkdir()
    (source / "nested").mkdir()
    (source / "nested/file").write_text("content")
    capture.copy_source(source, staging / "world", inherited_private=True)

    def identities(path):
        descriptor = win32security.GetNamedSecurityInfo(
            str(path),
            win32security.SE_FILE_OBJECT,
            win32security.DACL_SECURITY_INFORMATION,
        )
        acl = descriptor.GetSecurityDescriptorDacl()
        assert acl is not None
        return {str(acl.GetAce(i)[2]) for i in range(acl.GetAceCount())}

    allowed = identities(staging)
    assert identities(staging / "world") == allowed
    assert identities(staging / "world/nested/file") == allowed


async def test_archive_file_is_flushed_once_before_publication(
    populated_server, monkeypatch
):
    calls = []
    original = os.fsync

    def observed(descriptor):
        metadata = os.fstat(descriptor)
        calls.append((metadata.st_dev, metadata.st_ino))
        return original(descriptor)

    monkeypatch.setattr(os, "fsync", observed)
    backup = await populated_server.backups.create_snapshot(mode="world")
    metadata = populated_server.backups.resolve_backup(backup.backup_id).stat()
    assert calls.count((metadata.st_dev, metadata.st_ino)) == 1


def test_payload_reader_measures_only_read_calls(monkeypatch):
    import io

    from bedrock_server_manager.backups import archive

    ticks = iter([1.0, 1.25, 10.0, 10.5])
    monkeypatch.setattr(archive.time, "perf_counter", lambda: next(ticks))
    with archive._MeasuredReader(io.BytesIO(b"abcdef")) as reader:
        assert reader.read(2) == b"ab"
        assert reader.read() == b"cdef"
        assert reader.read_seconds == 0.75
        assert reader.bytes_read == 6


@pytest.mark.parametrize("invalidate", [False, True])
@pytest.mark.parametrize("mode", ["world", "full", "selected"])
async def test_spooled_capture_recovery_and_fallback(
    populated_server, monkeypatch, mode, invalidate, caplog
):
    from pathlib import Path

    original = capture.build_payload
    original_open = Path.open
    observed = []

    def build(*args, **kwargs):
        spool = kwargs["spool"]
        assert spool.entries
        observed.append(spool.path)
        if invalidate:
            spool.entries = {
                path: (size, -1, offset)
                for path, (size, modified, offset) in spool.entries.items()
            }

        def guarded_open(path, *open_args, **open_kwargs):
            if not invalidate and path in spool.entries:
                pytest.fail("Archive creation reopened a spooled staged file")
            return original_open(path, *open_args, **open_kwargs)

        with monkeypatch.context() as patch:
            patch.setattr(Path, "open", guarded_open)
            return original(*args, **kwargs)

    caplog.set_level("DEBUG")
    monkeypatch.setattr(capture, "build_payload", build)
    options = (
        {"components": ["world", "server.properties", "bsm_settings"]}
        if mode == "selected"
        else {}
    )
    backup = await populated_server.backups.create_snapshot(mode=mode, **options)
    verified = await populated_server.backups.verify_snapshot(backup.backup_id)
    assert verified.status == "verified"
    assert not observed[0].exists()
    message = next(
        record.message
        for record in caplog.records
        if record.message.startswith("Backup payload completed:")
    )
    assert ("spooled_files=0 " in message) is invalidate


async def test_spool_cleanup_when_payload_is_canceled(populated_server, monkeypatch):
    observed = []

    def canceled(*args, **kwargs):
        spool = kwargs["spool"]
        assert spool.entries
        observed.append(spool)
        raise InterruptedError("Capture canceled")

    monkeypatch.setattr(capture, "build_payload", canceled)
    with pytest.raises(Exception):
        await populated_server.backups.create_snapshot(mode="world")
    assert observed[0].stream.closed
    assert not observed[0].path.exists()
