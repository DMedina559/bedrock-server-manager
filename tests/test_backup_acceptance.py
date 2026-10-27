"""Recovery acceptance and injected filesystem failures exercise real archive I/O."""

import asyncio
import errno
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from bedrock_server_manager.backups.assurance import cleanup_destination
from bedrock_server_manager.backups.models import BASE_COMPONENTS, PACK_COMPONENTS
from bedrock_server_manager.backups.recovery import RestoreJournal
from bedrock_server_manager.backups.reports import recovery_report
from bedrock_server_manager.error import BackupRestoreError


async def test_report_excludes_credentials_names_paths_and_values(populated_server):
    server = populated_server
    root = Path(server.paths.server_dir)
    (root / "config").mkdir(exist_ok=True)
    (root / "config" / "private-secret-name.json").write_text(
        '{"token":"sensitive-value"}'
    )
    key = server.backups.credentials.rotate()
    snapshot = await server.backups.create_snapshot(encrypted=True)
    await server.backups.annotate_snapshot(
        snapshot.backup_id, "private-label", "private-notes"
    )
    plan = await server.backups.plan_restore(
        snapshot.backup_id, ["script_config"], dry_run=True
    )
    await server.backups.restore_snapshot(
        snapshot.backup_id, plan.components, plan.token
    )
    report = await recovery_report(server.backups)
    body = report.model_dump_json()
    for secret in [
        key.secret.get_secret_value(),
        snapshot.filename,
        server.server_name,
        str(root),
        "private-secret-name",
        "sensitive-value",
        "private-label",
        "private-notes",
    ]:
        assert secret not in body
    assert report.last_review.components == ["script_config"]
    assert report.last_review.volumes
    assert report.last_restore.committed
    assert report.last_restore.status == "completed"


@pytest.mark.parametrize("failure", [errno.ENOSPC, errno.EACCES, "cancel"])
async def test_mid_restore_failures_roll_back_exactly(
    populated_server, monkeypatch, failure
):
    server = populated_server
    root = Path(server.paths.server_dir)
    snapshot = await server.backups.create_snapshot()
    properties = root / "server.properties"
    properties.write_text(
        properties.read_text() + "\nserver-name=keep-this-current-value\n"
    )
    before = properties.read_bytes()
    plan = await server.backups.plan_restore(snapshot.backup_id, ["server.properties"])
    replace = RestoreJournal.replace

    def failing_replace(journal, index, source):
        replace(journal, index, source)
        if failure == "cancel":
            raise asyncio.CancelledError
        raise OSError(failure, "Injected filesystem failure")

    monkeypatch.setattr(RestoreJournal, "replace", failing_replace)
    with pytest.raises(asyncio.CancelledError if failure == "cancel" else OSError):
        await server.backups.restore_snapshot(
            snapshot.backup_id, plan.components, plan.token
        )
    assert properties.read_bytes() == before
    assert not RestoreJournal(server).path.exists()
    report = await recovery_report(server.backups)
    assert report.last_restore.status == (
        "cancelled" if failure == "cancel" else "failed"
    )


async def test_disk_full_staging_does_not_stop_minecraft(populated_server, monkeypatch):
    server = populated_server
    snapshot = await server.backups.create_snapshot()
    plan = await server.backups.plan_restore(snapshot.backup_id, ["world"])
    original = server.backups.unpack_snapshot

    def no_space(path, destination, password=None):
        if ".bsm-restore-stage-" in str(destination):
            raise OSError(errno.ENOSPC, "No space")
        return original(path, destination, password)

    stop = AsyncMock()
    monkeypatch.setattr(server.backups, "unpack_snapshot", no_space)
    with pytest.raises(OSError):
        await server.backups.restore_snapshot(
            snapshot.backup_id, plan.components, plan.token, stop_server=stop
        )
    stop.assert_not_awaited()
    assert not RestoreJournal(server).path.exists()


async def test_disconnected_destination_keeps_local_archive_and_can_retry(
    populated_server, tmp_path
):
    server = populated_server
    snapshot = await server.backups.create_snapshot()
    destination = tmp_path / "nas"
    destination.mkdir()
    await server.settings.set(
        "backups.destinations", {"nas": {"path": str(destination)}}
    )
    destination.rmdir()
    with pytest.raises(BackupRestoreError):
        await server.backups.copy_snapshot(snapshot.backup_id, "nas")
    assert server.backups.resolve_backup(snapshot.backup_id).exists()
    destination.mkdir()
    await server.backups.copy_snapshot(snapshot.backup_id, "nas")
    assert (destination / server.server_name / snapshot.filename).exists()
    assert not list(destination.rglob(".bsm-copy-*"))


async def test_process_killed_after_external_unlink_does_not_recreate_copy(
    populated_server, tmp_path
):
    server = populated_server
    destination = tmp_path / "nas"
    destination.mkdir()
    config = {"nas": {"path": str(destination), "enabled": True, "keep_count": 1}}
    await server.settings.set("backups.destinations", config)
    first = await server.backups.create_snapshot()
    await server.backups.create_snapshot()
    script = """
import json, sys
from pathlib import Path
from types import SimpleNamespace
from bedrock_server_manager.backups.catalog import BackupCatalog
from bedrock_server_manager.backups.assurance import cleanup_preview, apply_cleanup
local, destination, name, config = sys.argv[1:]
class Owner:
    server = SimpleNamespace(server_name=name)
    catalog = BackupCatalog(Path(local))
    def _directory(self): return local
    def destination_configs(self): return json.loads(config)
backups = Owner()
plan = cleanup_preview(backups, "nas")
unlink = Path.unlink
def interrupted(path, *args, **kwargs):
    unlink(path, *args, **kwargs)
    if path.parent == Path(destination) / name:
        print("unlinked", flush=True)
        sys.stdin.read()
Path.unlink = interrupted
apply_cleanup(backups, "nas", plan)
"""
    process = subprocess.Popen(
        [
            sys.executable,
            "-c",
            script,
            server.backups._directory(),
            str(destination),
            server.server_name,
            json.dumps(config),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert (
            await asyncio.wait_for(asyncio.to_thread(process.stdout.readline), 20)
            == "unlinked\n"
        )
        process.kill()
        await asyncio.to_thread(process.wait, 10)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=10)
        for stream in (process.stdin, process.stdout, process.stderr):
            stream.close()
    assert not (destination / server.server_name / first.filename).exists()
    await server.settings.set("backups.recovery_drill_interval_hours", 0)
    await server.backups.maintain_backups()
    assert not (destination / server.server_name / first.filename).exists()
    await cleanup_destination(server.backups, "nas")
    value = server.backups.catalog.load()
    assert not value["destinations"]["nas"]["pending_delete"]
    assert first.backup_id not in value["destinations"]["nas"]["archives"]


async def test_encrypted_restore_on_fresh_install_needs_only_archive_and_kit(
    populated_server, tmp_path, dummy_server_zip
):
    from bedrock_server_manager.api.install import install_new_server
    from bedrock_server_manager.api.models import InstallNewServerRequest
    from bedrock_server_manager.backups.archive import digest
    from bedrock_server_manager.backups.credentials import private_directory
    from bedrock_server_manager.backups.models import PREFIXES, ServerSettingsExport
    from bedrock_server_manager.backups.recovery import apply_settings
    from bedrock_server_manager.config import bcm_config
    from bedrock_server_manager.context import AppContext
    from bedrock_server_manager.db.database import Database
    from bedrock_server_manager.utils.general import startup_checks

    source = populated_server
    source_root = Path(source.paths.server_dir)
    (source_root / "config").mkdir(exist_ok=True)
    (source_root / "config" / "variables.json").write_text('{"secret":"recover-me"}')
    (source_root / "behavior_packs").mkdir(exist_ok=True)
    (source_root / "behavior_packs" / "manifest.json").write_text(
        '{"pack":"recover-me"}'
    )
    await apply_settings(
        source,
        ServerSettingsExport(
            autostart=False,
            autoupdate=True,
            target_version="LATEST",
            custom={"recovery": "server-row"},
        ),
    )
    source.backups.credentials.rotate()
    kit = source.backups.credentials.emergency_kit()
    password = next(
        line.removeprefix("Recovery key: ")
        for line in kit.splitlines()
        if line.startswith("Recovery key: ")
    )
    captured = await source.backups.create_snapshot(
        encrypted=True, components=list(BASE_COMPONENTS + PACK_COMPONENTS)
    )
    portable = source.backups.resolve_backup(captured.backup_id).read_bytes()
    old_config, old_data = bcm_config.get_config_dir(), source.settings.data_dir
    fresh_data, fresh_config = tmp_path / "fresh-data", tmp_path / "fresh-config"
    fresh_data.mkdir()
    fresh_config.mkdir()
    (fresh_config / "bedrock_server_manager.json").write_text(
        json.dumps(
            {
                "data_dir": str(fresh_data),
                "db_url": f"sqlite:///{fresh_data / 'fresh.db'}",
            }
        )
    )
    context = AppContext()
    database = Database(f"sqlite+aiosqlite:///{fresh_data / 'fresh.db'}")
    try:
        bcm_config.set_custom_config_dir(str(fresh_config))
        bcm_config.set_custom_data_dir(str(fresh_data))
        context._db = database
        await context.load()
        context.loop = asyncio.get_running_loop()
        startup_checks(context)
        assert not context.state.servers.servers
        installer = dummy_server_zip(target_dir=tmp_path / "fresh-installer")
        await install_new_server(
            InstallNewServerRequest(
                server_name="recovered",
                target_version="CUSTOM",
                server_zip_path=str(installer),
            ),
            app_context=context,
        )
        target = context.get_server("recovered")
        assert not target.backups.credentials.metadata()["keys"]
        root = Path(target.paths.server_dir)
        (root / "permissions.json").write_text(
            '[{"xuid":"keep-target","permission":"member"}]'
        )
        unselected = (root / "permissions.json").read_bytes()
        destination = (
            private_directory(Path(target.backups._directory())) / captured.filename
        )
        destination.write_bytes(portable)
        selected = [
            "world",
            "server.properties",
            "script_config",
            "bsm_settings",
            "behavior_packs",
        ]
        plan = await target.backups.plan_restore(captured.filename, selected, password)
        result = await target.backups.restore_snapshot(
            captured.filename, selected, plan.token, password
        )
        assert result.committed
        assert target.server_name == "recovered"
        assert target.configuration.snapshot().custom == {"recovery": "server-row"}
        assert (root / "permissions.json").read_bytes() == unselected
        for item in captured.manifest.files:
            if item.component in selected and item.component != "bsm_settings":
                prefix = PREFIXES[item.component]
                relative = item.path.removeprefix(prefix).lstrip("/")
                restored = root / plan.destinations[item.component]
                if relative:
                    restored /= relative
                assert digest(restored) == item.sha256
        assert not target.backups.credentials.metadata()["keys"]
        # Its encrypted safety archive is also recoverable with the same kit.
        assert (
            await target.backups.inspect_snapshot(result.safety_backup_id, password)
        ).manifest.reason == "pre_restore"
    finally:
        await context.shutdown()
        await database.shutdown()
        bcm_config.set_custom_config_dir(old_config)
        bcm_config.set_custom_data_dir(old_data)
