import os
from pathlib import Path

import pytest

from bedrock_server_manager.error import BackupRestoreError


async def test_server_backup_directory(real_bedrock_server, app_context):
    """Test generating the server backup directory."""
    server = real_bedrock_server
    expected_dir = os.path.join(
        app_context.settings.get("paths.backups"), server.server_name
    )
    assert server.backups.server_backup_directory == expected_dir


async def test_legacy_config_backup_restores(real_bedrock_server):
    from pathlib import Path

    server = real_bedrock_server
    directory = Path(server.backups.server_backup_directory)
    directory.mkdir(parents=True, exist_ok=True)
    backup = directory / "server_backup_20250101_120000.properties"
    backup.write_text("level-name=legacy\n")
    await server.backups.restore_config(str(backup))
    assert await server.get_world_name() == "legacy"


"""Portable archive capture and selective restore integration coverage."""


async def test_snapshot_restores_selected_files_and_database_settings(populated_server):
    server = populated_server
    root = Path(server.paths.server_dir)
    (root / "config" / "module").mkdir(parents=True)
    (root / "config" / "module" / "secrets.json").write_text('{"secret":"original"}')
    await server.set_autostart(True)
    snapshot = await server.backups.create_snapshot()
    assert snapshot.manifest.components["script_config"] == "included"
    assert snapshot.manifest.components["world"] == "included"
    await server.set_autostart(False)
    (root / "config" / "module" / "secrets.json").write_text("changed")
    (root / "config" / "extra.txt").write_text("remove on restore")
    properties = (root / "server.properties").read_bytes()
    selected = ["script_config", "bsm_settings"]
    plan = await server.backups.plan_restore(snapshot.backup_id, selected)
    result = await server.backups.restore_snapshot(
        snapshot.backup_id, selected, plan.token
    )
    assert result.committed
    assert server.configuration.snapshot().autostart
    assert (
        root / "config" / "module" / "secrets.json"
    ).read_text() == '{"secret":"original"}'
    assert not (root / "config" / "extra.txt").exists()
    assert (root / "server.properties").read_bytes() == properties


async def test_encrypted_snapshot_hides_secrets_and_supports_old_keys(populated_server):
    server = populated_server
    key = server.backups.credentials.rotate()
    snapshot = await server.backups.create_snapshot(encrypted=True)
    contents = (
        Path(server.backups.server_backup_directory) / snapshot.filename
    ).read_bytes()
    assert b"server.properties" not in contents
    assert key.secret.get_secret_value().encode() not in contents
    server.backups.credentials.rotate()
    inspection = await server.backups.inspect_snapshot(snapshot.backup_id)
    assert inspection.manifest.backup_id == snapshot.manifest.backup_id
    with pytest.raises(BackupRestoreError):
        await server.backups.inspect_snapshot(snapshot.backup_id, "wrong-key")
    assert "Recovery key:" in server.backups.credentials.emergency_kit(key.key_id)


async def test_stale_plan_rejected_without_changes(populated_server):
    server = populated_server
    snapshot = await server.backups.create_snapshot()
    plan = await server.backups.plan_restore(snapshot.backup_id, ["server.properties"])
    properties = Path(server.paths.server_properties_path)
    properties.write_text(properties.read_text() + "\nserver-name=changed\n")
    with pytest.raises(BackupRestoreError, match="stale"):
        await server.backups.restore_snapshot(
            snapshot.backup_id, ["server.properties"], plan.token
        )
    assert "changed" in properties.read_text()


async def test_retention_zero_preserves_published_archive(populated_server):
    server = populated_server
    await server.settings.set("retention.backups", 0)
    for _ in range(2):
        await server.backups.create_snapshot()
    assert len(await server.backups.list_snapshots()) == 2


async def test_missing_encryption_key_does_not_publish(populated_server):
    with pytest.raises(Exception, match="key"):
        await populated_server.backups.create_snapshot(encrypted=True)
    assert await populated_server.backups.list_snapshots() == []


async def test_restore_failure_rolls_back_every_selected_file(
    populated_server, monkeypatch
):
    from bedrock_server_manager.backups.recovery import RestoreJournal

    server = populated_server
    root = Path(server.paths.server_dir)
    snapshot = await server.backups.create_snapshot()
    properties = root / "server.properties"
    properties.write_text(properties.read_text() + "\nserver-name=before-restore\n")
    allowlist = root / "allowlist.json"
    allowlist.write_text('[{"name":"keep-current","xuid":"123"}]')
    originals = {p: p.read_bytes() for p in (properties, allowlist)}
    selected = ["server.properties", "allowlist.json"]
    plan = await server.backups.plan_restore(snapshot.backup_id, selected)
    replace = RestoreJournal.replace

    def fail_second(self, index, source):
        if index == 1:
            raise OSError("injected replacement failure")
        return replace(self, index, source)

    monkeypatch.setattr(RestoreJournal, "replace", fail_second)
    with pytest.raises(OSError):
        await server.backups.restore_snapshot(snapshot.backup_id, selected, plan.token)
    assert all(path.read_bytes() == value for path, value in originals.items())
    assert not (root / ".bsm-restore").exists()


async def test_interrupted_restore_recovers_before_server_start(
    populated_server, tmp_path
):
    from bedrock_server_manager.backups.recovery import RestoreJournal

    server = populated_server
    properties = Path(server.paths.server_properties_path)
    original = properties.read_bytes()
    journal = RestoreJournal(server)
    journal.begin(["server.properties"], True)
    replacement = tmp_path / "replacement"
    replacement.write_text("level-name=wrong\n")
    journal.replace(0, replacement)
    await server.set_autostart(True)
    with pytest.raises(BackupRestoreError, match="unfinished"):
        await server.start()
    await journal.recover()
    assert properties.read_bytes() == original
    assert not server.configuration.snapshot().autostart
    assert not journal.path.exists()


async def test_committed_restore_recovery_preserves_new_files(
    populated_server, tmp_path
):
    from bedrock_server_manager.backups.recovery import RestoreJournal

    server = populated_server
    journal = RestoreJournal(server)
    journal.begin(["allowlist.json"], False)
    replacement = tmp_path / "replacement"
    replacement.write_text("[]")
    journal.replace(0, replacement)
    journal.commit()
    await journal.recover()
    assert Path(server.paths.allowlist_json_path).read_text() == "[]"
    assert not journal.path.exists()


async def test_database_failure_rolls_back_files_and_preserves_settings(
    populated_server, monkeypatch
):
    from bedrock_server_manager.db.storage import Storage

    server = populated_server
    snapshot = await server.backups.create_snapshot()
    await server.set_autostart(True)
    properties = Path(server.paths.server_properties_path)
    properties.write_text(properties.read_text() + "\nserver-name=keep\n")
    original = properties.read_bytes()
    selected = ["server.properties", "bsm_settings"]
    plan = await server.backups.plan_restore(snapshot.backup_id, selected)
    commit = Storage.commit_record
    attempts = 0

    async def fail_once(self, *args, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise OSError("injected database error")
        return await commit(self, *args, **kwargs)

    monkeypatch.setattr(Storage, "commit_record", fail_once)
    with pytest.raises(OSError):
        await server.backups.restore_snapshot(snapshot.backup_id, selected, plan.token)
    assert properties.read_bytes() == original
    assert server.configuration.snapshot().autostart


async def test_restore_maintenance_rejects_independent_settings_writer(
    populated_server,
):
    import asyncio

    from bedrock_server_manager.error import OperationConflictError
    from bedrock_server_manager.services.server_service import ServerService

    server = populated_server
    guard = server.state.servers.maintenance(server.server_name)
    entered = asyncio.Event()
    release = asyncio.Event()

    async def restoring():
        with guard.hold():
            entered.set()
            await release.wait()
            await server.set_autostart(True)

    task = asyncio.create_task(restoring())
    await entered.wait()
    try:
        with pytest.raises(OperationConflictError):
            await ServerService(server.state, server.storage).set_autoupdate(
                server.server_name, True
            )
    finally:
        release.set()
        await task
    assert server.configuration.snapshot().autostart
    assert not server.configuration.snapshot().autoupdate
