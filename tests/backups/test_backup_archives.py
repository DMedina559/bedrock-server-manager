"""Archive validation and offline recovery exercise the actual portable format."""

import io
import tarfile
from pathlib import Path

import pytest
from click.testing import CliRunner

from bedrock_server_manager.__main__ import create_cli_app
from bedrock_server_manager.backups.archive import safe_name
from bedrock_server_manager.error import BackupRestoreError
from bedrock_server_manager.plugins.files import read_plugin_json, write_plugin_json


@pytest.mark.parametrize(
    "name",
    [
        "../escape",
        "/absolute",
        "C:/absolute",
        "world\\escape",
        "world/CON.txt",
        "world/thing.",
        "world/a:b",
        "world//file",
        "world/./file",
    ],
)
def test_portable_paths_reject_unsafe_names(name):
    with pytest.raises(BackupRestoreError):
        safe_name(name)


async def test_offline_encrypted_extraction_requires_no_database(
    populated_server, tmp_path
):
    key = populated_server.backups.credentials.rotate()
    snapshot = await populated_server.backups.create_snapshot(encrypted=True)
    source = Path(populated_server.backups.server_backup_directory) / snapshot.filename
    destination = tmp_path / "offline"
    result = CliRunner().invoke(
        create_cli_app(),
        [
            "--db-url",
            "unavailable://",
            "backup",
            "extract",
            str(source),
            str(destination),
            "--recovery-key",
        ],
        input=key.secret.get_secret_value() + "\n",
    )
    assert result.exit_code == 0, result.output
    assert (destination / "world" / "level.dat").exists()
    assert (destination / "manifest.json").exists()
    assert not (destination / "credentials").exists()


async def test_corrupt_encrypted_backup_does_not_restore(populated_server):
    server = populated_server
    server.backups.credentials.rotate()
    snapshot = await server.backups.create_snapshot(encrypted=True)
    path = Path(server.backups.server_backup_directory) / snapshot.filename
    with tarfile.open(path) as source:
        first, payload = source.getmembers()
        metadata = source.extractfile(first).read()
        content = bytearray(source.extractfile(payload).read())
    content[-1] ^= 1
    with tarfile.open(path, "w") as archive:
        first.size = len(metadata)
        archive.addfile(first, io.BytesIO(metadata))
        payload.size = len(content)
        archive.addfile(payload, io.BytesIO(content))
    properties = Path(server.paths.server_properties_path).read_bytes()
    with pytest.raises(BackupRestoreError):
        await server.backups.plan_restore(snapshot.backup_id, ["server.properties"])
    assert Path(server.paths.server_properties_path).read_bytes() == properties


async def test_archive_inventory_rejects_extra_file(populated_server):

    server = populated_server
    snapshot = await server.backups.create_snapshot()
    path = Path(server.backups.server_backup_directory) / snapshot.filename
    with tarfile.open(path) as outer:
        metadata = outer.extractfile("bsm.json").read()
        compressed = outer.extractfile("payload.tar.gz").read()
    output = io.BytesIO()
    with (
        tarfile.open(fileobj=io.BytesIO(compressed), mode="r:gz") as source,
        tarfile.open(fileobj=output, mode="w:gz") as target,
    ):
        for member in source:
            target.addfile(
                member, source.extractfile(member) if member.isfile() else None
            )
        extra = tarfile.TarInfo("server-config/undeclared-secret")
        extra.size = 1
        target.addfile(extra, io.BytesIO(b"x"))
    with tarfile.open(path, "w") as outer:
        for name, content in (
            ("bsm.json", metadata),
            ("payload.tar.gz", output.getvalue()),
        ):
            member = tarfile.TarInfo(name)
            member.size = len(content)
            outer.addfile(member, io.BytesIO(content))
    with pytest.raises(BackupRestoreError):
        await server.backups.inspect_snapshot(snapshot.backup_id)


def test_plugin_files_are_owner_scoped(tmp_path):
    write_plugin_json(str(tmp_path), "first", "settings.json", {"value": 1})
    assert read_plugin_json(str(tmp_path), "first", "settings.json") == {"value": 1}
    with pytest.raises(BackupRestoreError):
        read_plugin_json(str(tmp_path), "first", "../second/settings.json")
    with pytest.raises(BackupRestoreError):
        read_plugin_json(
            str(tmp_path), "first", "../../../credentials/backup-keys.json"
        )


async def test_restore_preview_redacts_secrets_and_retains_safety_backup(
    populated_server,
):
    server = populated_server
    properties = Path(server.paths.server_properties_path)
    properties.write_text(
        properties.read_text() + "\nserver-name=original\nprivate-token=old-secret\n"
    )
    snapshot = await server.backups.create_snapshot()
    properties.write_text(
        properties.read_text()
        .replace("server-name=original", "server-name=changed")
        .replace("old-secret", "new-secret")
    )
    plan = await server.backups.plan_restore(snapshot.backup_id, ["server.properties"])
    assert plan.change_counts["replaced"] == 1
    assert "old-secret" not in plan.model_dump_json()
    assert "new-secret" not in plan.model_dump_json()
    assert any(
        change.key == "server-name" and change.before == "changed"
        for change in plan.setting_changes
    )
    before = properties.read_bytes()
    result = await server.backups.restore_snapshot(
        snapshot.backup_id, ["server.properties"], plan.token
    )
    safety = next(
        item
        for item in await server.backups.list_snapshots()
        if item.backup_id == result.safety_backup_id
    )
    assert safety.purpose == "pre_restore" and safety.protected_until
    undo = await server.backups.plan_restore(safety.backup_id, ["server.properties"])
    await server.backups.restore_snapshot(
        safety.backup_id, ["server.properties"], undo.token
    )
    assert properties.read_bytes() == before


async def test_verification_failure_and_recovery_key_health(populated_server):
    server = populated_server
    await server.settings.set("backups.verify_after_create", True)
    original = server.backups.credentials.rotate()
    archive = await server.backups.create_snapshot(encrypted=True)
    server.backups.credentials.rotate()
    health = await server.backups.backup_health()
    assert health.older_key_ids == [original.key_id]
    assert not health.missing_key_ids
    with pytest.raises(BackupRestoreError):
        await server.backups.verify_snapshot(
            archive.backup_id, "wrong", record_failure=False
        )
    assert (await server.backups.list_snapshots())[0].verification.status == "verified"
    path = server.backups.resolve_backup(archive.backup_id)
    path.write_bytes(b"corrupt")
    with pytest.raises(BackupRestoreError):
        await server.backups.verify_snapshot(archive.backup_id)
    assert (await server.backups.backup_health()).failed_count == 1


async def test_destination_copy_preserves_encryption_and_retries(
    populated_server, tmp_path
):
    server = populated_server
    server.backups.credentials.rotate()
    destination = tmp_path / "remote"
    await server.settings.set(
        "backups.destinations", {"nas": {"path": str(destination), "enabled": True}}
    )
    archive = await server.backups.create_snapshot(encrypted=True)
    assert server.backups.resolve_backup(archive.backup_id).is_file()
    assert (await server.backups.list_snapshots())[0].copies["nas"].status == "failed"
    destination.mkdir()
    await server.backups.copy_snapshot(archive.backup_id, "nas")
    copied = destination / server.server_name / archive.filename
    assert (
        copied.read_bytes()
        == server.backups.resolve_backup(archive.backup_id).read_bytes()
    )
    assert (await server.backups.list_snapshots())[0].copies[
        "nas"
    ].status == "completed"
    copied.write_bytes(b"different content")
    with pytest.raises(BackupRestoreError):
        await server.backups.copy_snapshot(archive.backup_id, "nas")
    assert copied.read_bytes() == b"different content"


async def test_pins_safety_windows_and_last_usable_backup_survive_budget(
    populated_server,
):
    server = populated_server
    await server.settings.set("retention.backups", 0)
    first = await server.backups.create_snapshot()
    await server.backups.pin_snapshot(first.backup_id, True)
    second = await server.backups.create_snapshot(purpose="pre_restore")
    third = await server.backups.create_snapshot()
    server.backups.resolve_backup(third.backup_id).write_bytes(b"bad archive")
    await server.settings.set("retention.backups", 1)
    await server.settings.set("backups.storage_budget_bytes", 1)
    await server.backups.prune_snapshots()
    assert {i.backup_id for i in await server.backups.list_snapshots()} == {
        first.backup_id,
        second.backup_id,
        third.backup_id,
    }


async def test_disk_exhaustion_never_replaces_destination(
    populated_server, monkeypatch
):
    from collections import namedtuple

    import bedrock_server_manager.backups.server as module

    server = populated_server
    archive = await server.backups.create_snapshot()
    properties = Path(server.paths.server_properties_path)
    properties.write_text(properties.read_text() + "\nserver-name=keep\n")
    before = properties.read_bytes()
    plan = await server.backups.plan_restore(archive.backup_id, ["server.properties"])
    usage = namedtuple("usage", "total used free")
    monkeypatch.setattr(module.shutil, "disk_usage", lambda _: usage(100, 100, 0))
    with pytest.raises(BackupRestoreError, match="Insufficient space"):
        await server.backups.restore_snapshot(
            archive.backup_id, ["server.properties"], plan.token
        )
    assert properties.read_bytes() == before
    assert not (Path(server.paths.server_dir) / ".bsm-restore").exists()


async def test_prepare_new_server_remaps_ports_without_restoring_source(
    populated_server, app_context, dummy_server_zip, tmp_path, monkeypatch
):
    from bedrock_server_manager.api import install
    from bedrock_server_manager.api.backup_restore import prepare_backup_copy
    from bedrock_server_manager.api.models.backup_restore import (
        PrepareBackupCopyRequest,
    )

    server = populated_server
    snapshot = await server.backups.create_snapshot()
    original = Path(server.paths.server_properties_path).read_bytes()
    production_install = install.install_new_server
    archive = dummy_server_zip(target_dir=tmp_path)

    async def local_install(request, *, app_context):
        return await production_install(
            request.model_copy(
                update={"target_version": "CUSTOM", "server_zip_path": str(archive)}
            ),
            app_context=app_context,
        )

    monkeypatch.setattr(install, "install_new_server", local_install)
    prepared = await prepare_backup_copy(
        PrepareBackupCopyRequest(
            server_name=server.server_name,
            backup_id=snapshot.backup_id,
            target_server="recovered",
            server_port=19142,
            server_portv6=19143,
        ),
        app_context=app_context,
    )
    target = app_context.get_server("recovered")
    assert not await target.is_running()
    assert Path(server.paths.server_properties_path).read_bytes() == original
    inspected = await target.backups.inspect_snapshot(prepared.backup_id)
    assert inspected.manifest.source_server == server.server_name
    plan = await target.backups.plan_restore(
        prepared.backup_id, ["world", "server.properties", "bsm_settings"]
    )
    await target.backups.restore_snapshot(
        prepared.backup_id, plan.components, plan.token
    )
    assert "server-port=19142" in Path(target.paths.server_properties_path).read_text()
    assert (
        "server-portv6=19143" in Path(target.paths.server_properties_path).read_text()
    )
    assert not target.configuration.snapshot().autostart
    assert (
        Path(target.paths.server_dir) / "worlds" / "Bedrock level" / "level.dat"
    ).is_file() or any((Path(target.paths.server_dir) / "worlds").rglob("level.dat"))


async def test_periodic_verification_detects_corrupt_archive(populated_server):
    server = populated_server
    snapshot = await server.backups.create_snapshot()
    catalog = server.backups.catalog
    catalog.update(
        snapshot.backup_id,
        verification={"status": "verified", "verified_at": "2000-01-01T00:00:00+00:00"},
    )
    server.backups.resolve_backup(snapshot.backup_id).write_bytes(b"corrupt archive")
    await server.backups.maintain_backups()
    assert (await server.backups.backup_health()).failed_count == 1


async def test_locked_file_failure_preserves_restore_data(
    populated_server, monkeypatch
):
    from bedrock_server_manager.backups.recovery import RestoreJournal

    server = populated_server
    snapshot = await server.backups.create_snapshot()
    path = Path(server.paths.server_properties_path)
    path.write_text(path.read_text() + "\nserver-name=preserve\n")
    before = path.read_bytes()
    plan = await server.backups.plan_restore(snapshot.backup_id, ["server.properties"])

    def locked(*args):
        raise PermissionError("File is locked by another process")

    monkeypatch.setattr(RestoreJournal, "replace", locked)
    with pytest.raises(PermissionError):
        await server.backups.restore_snapshot(
            snapshot.backup_id, ["server.properties"], plan.token
        )
    assert path.read_bytes() == before
    assert not (Path(server.paths.server_dir) / ".bsm-restore").exists()
    assert any(
        item.purpose == "pre_restore" for item in await server.backups.list_snapshots()
    )


async def test_safety_backup_does_not_block_repair_of_damaged_configuration(
    populated_server,
):
    server = populated_server
    snapshot = await server.backups.create_snapshot()
    properties = Path(server.paths.server_properties_path)
    properties.write_text("damaged configuration without a world name")
    plan = await server.backups.plan_restore(snapshot.backup_id, ["server.properties"])
    result = await server.backups.restore_snapshot(
        snapshot.backup_id, plan.components, plan.token
    )
    assert "level-name=" in properties.read_text()
    safety = next(
        item
        for item in await server.backups.list_snapshots()
        if item.backup_id == result.safety_backup_id
    )
    assert safety.pinned
    assert safety.verification.status == "failed"
    inspected = await server.backups.inspect_snapshot(safety.backup_id)
    assert inspected.manifest.components["server.properties"] == "included"


async def test_safety_archive_preserves_replaced_inactive_world(populated_server):
    import shutil

    server = populated_server
    root = Path(server.paths.server_dir)
    properties = Path(server.paths.server_properties_path)
    active = await server.get_world_name()
    original_properties = properties.read_text()
    other = "OtherWorld"
    shutil.copytree(root / "worlds" / active, root / "worlds" / other)
    properties.write_text(
        original_properties.replace(f"level-name={active}", f"level-name={other}")
    )
    snapshot = await server.backups.create_snapshot()
    properties.write_text(original_properties)
    old_active = (root / "worlds" / active / "level.dat").read_bytes()
    replaced = root / "worlds" / other / "level.dat"
    replaced.write_bytes(b"newer inactive world")
    plan = await server.backups.plan_restore(
        snapshot.backup_id, ["world", "server.properties"]
    )
    restored = await server.backups.restore_snapshot(
        snapshot.backup_id, plan.components, plan.token
    )
    undo = await server.backups.plan_restore(
        restored.safety_backup_id, ["world", "server.properties"]
    )
    assert undo.destinations["world"] == "worlds/OtherWorld"
    await server.backups.restore_snapshot(
        restored.safety_backup_id, undo.components, undo.token
    )
    assert replaced.read_bytes() == b"newer inactive world"
    assert (root / "worlds" / active / "level.dat").read_bytes() == old_active
    assert properties.read_text() == original_properties


async def test_safety_metadata_failure_after_commit_reports_restored_data(
    populated_server, monkeypatch
):
    from bedrock_server_manager.backups.catalog import BackupCatalog

    server = populated_server
    await server.settings.set("backups.verify_after_create", True)
    snapshot = await server.backups.create_snapshot()
    properties = Path(server.paths.server_properties_path)
    original = properties.read_bytes()
    properties.write_text(properties.read_text() + "\nserver-name=changed\n")
    plan = await server.backups.plan_restore(snapshot.backup_id, ["server.properties"])
    update = BackupCatalog.update

    def fail_unpin(self, identifier, **metadata):
        if metadata.get("pinned") is False:
            raise OSError("Metadata disk is full")
        return update(self, identifier, **metadata)

    monkeypatch.setattr(BackupCatalog, "update", fail_unpin)
    result = await server.backups.restore_snapshot(
        snapshot.backup_id, plan.components, plan.token
    )
    assert result.committed and result.cleanup_warning
    assert properties.read_bytes() == original
    assert next(
        item
        for item in await server.backups.list_snapshots()
        if item.backup_id == result.safety_backup_id
    ).pinned


@pytest.mark.parametrize("encrypted", [False, True])
async def test_capture_and_restore_flush_writable_file_handles(
    populated_server, monkeypatch, encrypted
):
    """Enforce Windows' writable-descriptor requirement even on POSIX runners."""
    import os
    import stat

    server = populated_server
    if encrypted:
        server.backups.credentials.rotate()
    original_fsync = os.fsync
    flushed = []

    def windows_fsync(descriptor):
        if stat.S_ISREG(os.fstat(descriptor).st_mode):
            # A zero-byte write leaves content unchanged and rejects read-only FDs.
            os.write(descriptor, b"")
            flushed.append(descriptor)
        return original_fsync(descriptor)

    monkeypatch.setattr(os, "fsync", windows_fsync)
    snapshot = await server.backups.create_snapshot(encrypted=encrypted)
    properties = Path(server.paths.server_properties_path)
    original = properties.read_bytes()
    properties.write_text(properties.read_text() + "\nserver-name=changed\n")
    plan = await server.backups.plan_restore(snapshot.backup_id, ["server.properties"])
    result = await server.backups.restore_snapshot(
        snapshot.backup_id, plan.components, plan.token
    )
    assert result.committed and result.safety_backup_id
    assert properties.read_bytes() == original
    assert len(flushed) >= 3


@pytest.mark.parametrize("compression", ["fast", "balanced", "small"])
async def test_compression_profiles_preserve_recovery(populated_server, compression):
    server = populated_server
    await server.settings.set("backups.compression", compression)
    backup = await server.backups.create_snapshot(mode="world")
    verified = await server.backups.verify_snapshot(backup.backup_id)
    assert verified.status == "verified"
    inspected = await server.backups.inspect_snapshot(backup.backup_id)
    assert inspected.manifest.mode == "world"
    assert "Compressing backup" in backup.stage_durations_ms
    assert "Recording archive integrity" in backup.stage_durations_ms
