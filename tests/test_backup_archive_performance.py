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
    populated_server, compression, encrypted
):
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
