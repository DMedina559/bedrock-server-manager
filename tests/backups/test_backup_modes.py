"""Exercise content boundaries and transactional full-directory restore."""

import os
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from bedrock_server_manager.api.backup_restore import create_server_backup
from bedrock_server_manager.backups.models import BASE_COMPONENTS
from bedrock_server_manager.backups.recovery import RestoreJournal
from bedrock_server_manager.backups.selection import selection
from bedrock_server_manager.error import BackupRestoreError
from bedrock_server_manager.events.operations import OperationName
from bedrock_server_manager.web.schemas.backup import SnapshotCreatePayload


async def test_capture_boundaries_sequence_reuse_and_backup_events(
    populated_server, app_context
):
    server = populated_server
    root = Path(server.paths.server_dir)
    (root / "behavior_packs").mkdir(exist_ok=True)
    (root / "behavior_packs" / "vanilla").write_text("bundled")
    world_dir = root / "worlds" / await server.get_world_name()
    (world_dir / "behavior_packs").mkdir(exist_ok=True)
    (world_dir / "behavior_packs" / "custom").write_text("world pack")

    # Default omits root packs but keeps world packs
    backup = await server.backups.create_snapshot()
    assert backup.manifest.selected_components == list(BASE_COMPONENTS)
    assert backup.manifest.components["behavior_packs"] == "absent"
    assert any(f.path.endswith("behavior_packs/custom") for f in backup.manifest.files)

    # World and selected capture boundaries
    world_snap = await server.backups.create_snapshot(mode="world")
    assert [
        c for c, state in world_snap.manifest.components.items() if state == "included"
    ] == ["world"]
    config_snap = await server.backups.create_snapshot(
        mode="selected", components=["server.properties"]
    )
    assert [
        c for c, state in config_snap.manifest.components.items() if state == "included"
    ] == ["server.properties"]
    with pytest.raises(BackupRestoreError):
        await server.backups.create_snapshot(mode="selected", components=[])

    # Sequence reuse requires requested coverage
    with server.operations.scope(
        OperationName.SERVER_START, server_name=server.server_name
    ):
        await server.backups.create_snapshot(mode="world")
        assert await server.backups.can_reuse_sequence_snapshot(mode="world")
        assert not await server.backups.can_reuse_sequence_snapshot(mode="full")
        assert not await server.backups.can_reuse_sequence_snapshot(
            mode="selected", components=["server.properties"]
        )

    # Current backup API dispatches the typed request and identity
    seen = []

    async def before(*, request, server_name, event, **kwargs):
        seen.append((server_name, request.mode))

    app_context.events.subscribe("before_backup", before, owner="core:test")
    await create_server_backup(
        {"server_name": server.server_name, "mode": "world"},
        app_context=app_context,
    )
    assert seen == [(server.server_name, "world")]


async def test_full_round_trip_rollbacks_and_refusals(populated_server, monkeypatch):
    server = populated_server
    root = Path(server.paths.server_dir)
    binary = root / "bedrock_server"
    binary.write_text("original executable")
    binary.chmod(0o700)
    (root / "second-world").mkdir()
    (root / "second-world" / "data").write_text("second world")

    snapshot = await server.backups.create_snapshot(mode="full")
    assert snapshot.manifest.components["server_directory"] == "included"
    assert snapshot.manifest.components["bsm_settings"] == "included"

    binary.write_text("changed")
    (root / "new-extra").write_text("remove me")
    plan = await server.backups.plan_restore(
        snapshot.backup_id, ["server_directory", "bsm_settings"]
    )
    assert any(c.path == "./new-extra" and c.action == "removed" for c in plan.changes)

    # First test rollback on replacement failure
    original_replace = RestoreJournal.replace

    def fail_after_first(self, index, source):
        original_replace(self, index, source)
        if index == 1:
            raise OSError("Injected replacement failure")

    with monkeypatch.context() as fault:
        fault.setattr(RestoreJournal, "replace", fail_after_first)
        with pytest.raises(OSError, match="Injected"):
            await server.backups.restore_snapshot(
                snapshot.backup_id, plan.components, plan.token
            )
    assert binary.read_text() == "changed"
    assert (root / "new-extra").read_text() == "remove me"
    assert not (root / ".bsm-restore").exists()

    # Now perform full restore successfully
    plan = await server.backups.plan_restore(
        snapshot.backup_id, ["server_directory", "bsm_settings"]
    )
    result = await server.backups.restore_snapshot(
        snapshot.backup_id, plan.components, plan.token
    )
    assert result.committed
    assert binary.read_text() == "original executable"
    assert not (root / "new-extra").exists()
    assert (root / "second-world" / "data").read_text() == "second world"
    if os.name != "nt":
        assert binary.stat().st_mode & 0o100
    safety = await server.backups.inspect_snapshot(result.safety_backup_id)
    assert safety.manifest.mode == "full"
    assert any(f.path == "server-directory/new-extra" for f in safety.manifest.files)

    # Refuses live or nested storage
    with monkeypatch.context() as fault:
        fault.setattr(server, "is_running", AsyncMock(return_value=True))
        with pytest.raises(BackupRestoreError, match="Stop the server"):
            await server.backups.create_snapshot(mode="full")

    await server.settings.set(
        "paths.backups", str(Path(server.paths.server_dir) / "backups")
    )
    with pytest.raises(BackupRestoreError, match="outside"):
        await server.backups.create_snapshot(mode="full")


def test_invalid_selections_and_http_payloads():
    dummy_settings = type(
        "Settings", (), {"get": lambda self, key, default=None: default}
    )()
    for mode, components in [
        ("world", ["world"]),
        ("selected", []),
        ("selected", ["world", "world"]),
        ("selected", ["server_directory"]),
    ]:
        with pytest.raises(BackupRestoreError):
            selection(dummy_settings, mode, components)

    for payload in [
        {"mode": "world", "components": ["world"]},
        {"mode": "selected", "components": []},
        {"mode": "full", "include_packs": True},
        {"mode": "selected", "components": ["server_directory"]},
    ]:
        with pytest.raises(ValidationError):
            SnapshotCreatePayload(**payload)


async def test_start_plugin_content_settings_reach_capture(
    populated_server, plugin_factory
):
    source = (
        Path(__file__).parents[2]
        / "src/bedrock_server_manager/plugins/default/backup_on_start.py"
    )
    plugin = await plugin_factory("backup_on_start", source.read_text())

    for mode, expected_components in [
        ("world", ["world"]),
        ("selected", ["server.properties"]),
        ("full", ["server_directory", "bsm_settings"]),
    ]:
        await plugin.set_plugin_setting("backup_mode", mode)
        if mode == "selected":
            await plugin.set_plugin_setting("components", ["server.properties"])
        await plugin.backup_on_start(server_name=populated_server.server_name)
        backups = await populated_server.backups.list_snapshots()
        latest = max(backups, key=lambda b: b.created_at)
        backup = await populated_server.backups.inspect_snapshot(latest.backup_id)
        assert backup.manifest.mode == mode
        assert backup.manifest.selected_components == expected_components
