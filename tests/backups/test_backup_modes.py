"""Exercise content boundaries and transactional full-directory restore."""

import os
from pathlib import Path

import pytest

from bedrock_server_manager.backups.models import BASE_COMPONENTS
from bedrock_server_manager.backups.selection import selection
from bedrock_server_manager.error import BackupRestoreError


async def test_default_omits_root_packs_but_keeps_world_packs(populated_server):
    server = populated_server
    root = Path(server.paths.server_dir)
    (root / "behavior_packs").mkdir(exist_ok=True)
    (root / "behavior_packs" / "vanilla").write_text("bundled")
    world = root / "worlds" / await server.get_world_name()
    (world / "behavior_packs").mkdir(exist_ok=True)
    (world / "behavior_packs" / "custom").write_text("world pack")
    backup = await server.backups.create_snapshot()
    assert backup.manifest.selected_components == list(BASE_COMPONENTS)
    assert backup.manifest.components["behavior_packs"] == "absent"
    assert any(f.path.endswith("behavior_packs/custom") for f in backup.manifest.files)


async def test_world_and_selected_capture_boundaries(populated_server):
    server = populated_server
    world = await server.backups.create_snapshot(mode="world")
    assert [
        c for c, state in world.manifest.components.items() if state == "included"
    ] == ["world"]
    config = await server.backups.create_snapshot(
        mode="selected", components=["server.properties"]
    )
    assert [
        c for c, state in config.manifest.components.items() if state == "included"
    ] == ["server.properties"]
    with pytest.raises(BackupRestoreError):
        await server.backups.create_snapshot(mode="selected", components=[])


async def test_full_round_trip_removes_extras_preserves_execute_and_safety(
    populated_server,
):
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


async def test_full_capture_refuses_live_or_nested_storage(
    populated_server, monkeypatch
):
    from unittest.mock import AsyncMock

    server = populated_server
    monkeypatch.setattr(server, "is_running", AsyncMock(return_value=True))
    with pytest.raises(BackupRestoreError, match="Stop the server"):
        await server.backups.create_snapshot(mode="full")
    monkeypatch.setattr(server, "is_running", AsyncMock(return_value=False))
    await server.settings.set(
        "paths.backups", str(Path(server.paths.server_dir) / "backups")
    )
    with pytest.raises(BackupRestoreError, match="outside"):
        await server.backups.create_snapshot(mode="full")


async def test_sequence_reuse_requires_requested_coverage(populated_server):
    from bedrock_server_manager.events.operations import OperationName

    server = populated_server
    with server.operations.scope(
        OperationName.SERVER_START, server_name=server.server_name
    ):
        await server.backups.create_snapshot(mode="world")
        assert await server.backups.can_reuse_sequence_snapshot(mode="world")
        assert not await server.backups.can_reuse_sequence_snapshot(mode="full")
        assert not await server.backups.can_reuse_sequence_snapshot(
            mode="selected", components=["server.properties"]
        )


@pytest.mark.parametrize(
    "mode,components",
    [
        ("world", ["world"]),
        ("selected", []),
        ("selected", ["world", "world"]),
        ("selected", ["server_directory"]),
    ],
)
def test_invalid_selections(mode, components):
    with pytest.raises(BackupRestoreError):
        selection(
            type("Settings", (), {"get": lambda self, key, default=None: default})(),
            mode,
            components,
        )


async def test_full_restore_failure_rolls_back_all_top_level_entries(
    populated_server, monkeypatch
):
    from bedrock_server_manager.backups.recovery import RestoreJournal

    server = populated_server
    root = Path(server.paths.server_dir)
    (root / "a-extra").write_text("captured")
    snapshot = await server.backups.create_snapshot(mode="full")
    (root / "a-extra").write_text("before restore")
    (root / "z-extra").write_text("keep on rollback")
    plan = await server.backups.plan_restore(snapshot.backup_id, ["server_directory"])
    original = RestoreJournal.replace

    def fail_after_first(self, index, source):
        original(self, index, source)
        if index == 1:
            raise OSError("Injected replacement failure")

    monkeypatch.setattr(RestoreJournal, "replace", fail_after_first)
    with pytest.raises(OSError, match="Injected"):
        await server.backups.restore_snapshot(
            snapshot.backup_id, plan.components, plan.token
        )
    assert (root / "a-extra").read_text() == "before restore"
    assert (root / "z-extra").read_text() == "keep on rollback"
    assert not (root / ".bsm-restore").exists()


@pytest.mark.parametrize(
    "payload",
    [
        {"mode": "world", "components": ["world"]},
        {"mode": "selected", "components": []},
        {"mode": "full", "include_packs": True},
        {"mode": "selected", "components": ["server_directory"]},
    ],
)
def test_invalid_http_selection_is_rejected_before_task_creation(payload):
    from pydantic import ValidationError

    from bedrock_server_manager.web.schemas.backup import SnapshotCreatePayload

    with pytest.raises(ValidationError):
        SnapshotCreatePayload(**payload)


async def test_legacy_backup_event_kwargs_preserve_40_shape(
    populated_server, app_context
):
    from bedrock_server_manager.api.backup_restore import backup_all

    seen = []

    async def before(*, request, server_name, event):
        seen.append((server_name, request.mode))

    # Exact legacy signature: new options stay accessible through request.
    app_context.events.subscribe("before_backup", before, owner="core:test")
    await backup_all(
        {"server_name": populated_server.server_name, "mode": "world"},
        app_context=app_context,
    )
    assert seen == [(populated_server.server_name, "world")]


@pytest.mark.parametrize("mode", ["world", "selected", "full"])
async def test_start_plugin_content_settings_reach_capture(
    populated_server, plugin_factory, mode
):
    source = (
        Path(__file__).parents[2]
        / "src/bedrock_server_manager/plugins/default/backup_on_start.py"
    )
    plugin = await plugin_factory("backup_on_start", source.read_text())
    if mode != "world":
        await plugin.set_plugin_setting("backup_mode", mode)
    if mode == "selected":
        await plugin.set_plugin_setting("components", ["server.properties"])
    await plugin.backup_on_start(server_name=populated_server.server_name)
    backups = await populated_server.backups.list_snapshots()
    assert len(backups) == 1
    backup = await populated_server.backups.inspect_snapshot(backups[0].backup_id)
    assert backup.manifest.mode == mode
    assert backup.manifest.selected_components == (
        {
            "world": ["world"],
            "selected": ["server.properties"],
            "full": ["server_directory", "bsm_settings"],
        }[mode]
    )
