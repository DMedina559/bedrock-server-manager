"""Exercise recovery evidence, redaction and reviewed external-copy deletion."""

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from bedrock_server_manager.backups.assurance import (
    cleanup_destination,
    maintain_assurance,
    recovery_drill,
)
from bedrock_server_manager.error import BackupRestoreError


async def configure(server, key, value):
    await server.settings.set(key, value)


async def test_readiness_and_drill_do_not_touch_live_files(populated_server):
    server = populated_server
    snapshot = await server.backups.create_snapshot()
    root = Path(server.paths.server_dir)
    before = (root / "server.properties").read_bytes()
    health = await server.backups.backup_health()
    assert health.readiness == "ready"
    assert health.recovery_backup_id == snapshot.backup_id
    result = await recovery_drill(server.backups, snapshot.backup_id)
    assert result["status"] == "passed" and result["checked_files"] > 0
    assert (root / "server.properties").read_bytes() == before
    assert not (root / ".bsm-restore").exists()
    assert (await server.backups.backup_health()).drill["status"] == "passed"


async def test_sensitive_access_changes_never_expose_values(populated_server):
    server = populated_server
    root = Path(server.paths.server_dir)
    (root / "permissions.json").write_text(
        '[{"xuid":"secret-player","permission":"operator"}]'
    )
    snapshot = await server.backups.create_snapshot()
    (root / "permissions.json").write_text("[]")
    plan = await server.backups.plan_restore(snapshot.backup_id, ["permissions.json"])
    assert plan.setting_changes
    assert "secret-player" not in plan.model_dump_json()
    assert "Sensitive values" in " ".join(plan.warnings)


async def test_cleanup_requires_current_preview_and_leaves_untracked_files(
    populated_server, tmp_path
):
    server = populated_server
    destination = tmp_path / "external"
    destination.mkdir()
    await configure(
        server,
        "backups.destinations",
        {"nas": {"path": str(destination), "keep_count": 1}},
    )
    first = await server.backups.create_snapshot()
    second = await server.backups.create_snapshot()
    external = destination / server.server_name
    untracked = external / "unrelated.bsmbackup"
    untracked.write_text("leave alone")
    plan = await cleanup_destination(server.backups, "nas")
    assert plan.delete == [first.backup_id]
    assert (external / first.backup_id).exists()
    await server.backups.pin_snapshot(first.backup_id, True)
    with pytest.raises(BackupRestoreError, match="changed"):
        await cleanup_destination(server.backups, "nas", plan.token)
    await server.backups.pin_snapshot(first.backup_id, False)
    plan = await cleanup_destination(server.backups, "nas")
    result = await cleanup_destination(server.backups, "nas", plan.token)
    assert result.applied
    assert not (external / first.backup_id).exists()
    assert (external / second.backup_id).exists()
    assert untracked.read_text() == "leave alone"
    assert (
        next(
            item
            for item in await server.backups.list_snapshots()
            if item.backup_id == first.backup_id
        )
        .copies["nas"]
        .status
        == "pruned"
    )


async def test_modified_external_copy_blocks_cleanup(populated_server, tmp_path):
    server = populated_server
    destination = tmp_path / "external"
    destination.mkdir()
    await configure(
        server,
        "backups.destinations",
        {"nas": {"path": str(destination), "keep_count": 1}},
    )
    snapshot = await server.backups.create_snapshot()
    (destination / server.server_name / snapshot.backup_id).write_text("modified")
    with pytest.raises(BackupRestoreError, match="changed"):
        await cleanup_destination(server.backups, "nas")


async def test_alerts_are_deduplicated_and_rearm_after_resolution(populated_server):
    server = populated_server
    await configure(server, "backups.recovery_drill_interval_hours", 0)
    server.events.emit = AsyncMock()
    await maintain_assurance(server.backups)
    assert server.events.emit.call_count == 1
    await maintain_assurance(server.backups)
    assert server.events.emit.call_count == 1
    await server.backups.create_snapshot()
    await maintain_assurance(server.backups)
    server.events.emit.reset_mock()
    for path in Path(server.backups._directory()).glob("*.bsmbackup"):
        path.unlink()
    await maintain_assurance(server.backups)
    assert server.events.emit.call_count == 1


async def test_external_index_survives_local_retention(populated_server, tmp_path):
    server = populated_server
    destination = tmp_path / "external"
    destination.mkdir()
    await configure(
        server,
        "backups.destinations",
        {"nas": {"path": str(destination), "keep_count": 1}},
    )
    first = await server.backups.create_snapshot()
    await server.backups.create_snapshot()
    await configure(server, "retention.backups", 1)
    await server.backups.prune_managed_snapshots()
    plan = await cleanup_destination(server.backups, "nas")
    assert first.backup_id in plan.delete


async def test_reconfigured_destination_requires_new_copy(populated_server, tmp_path):
    server = populated_server
    first_dir = tmp_path / "one"
    second_dir = tmp_path / "two"
    first_dir.mkdir()
    second_dir.mkdir()
    await configure(server, "backups.destinations", {"nas": {"path": str(first_dir)}})
    snapshot = await server.backups.create_snapshot()
    assert (await server.backups.backup_health()).readiness == "ready"
    await configure(server, "backups.destinations", {"nas": {"path": str(second_dir)}})
    assert (await server.backups.backup_health()).readiness == "attention"
    await configure(server, "backups.recovery_drill_interval_hours", 0)
    await server.backups.maintain_backups()
    assert (second_dir / server.server_name / snapshot.backup_id).is_file()
    assert (await server.backups.backup_health()).readiness == "ready"


async def test_missing_external_copy_is_not_reported_ready(populated_server, tmp_path):
    server = populated_server
    destination = tmp_path / "external"
    destination.mkdir()
    await configure(server, "backups.destinations", {"nas": {"path": str(destination)}})
    snapshot = await server.backups.create_snapshot()
    (destination / server.server_name / snapshot.backup_id).unlink()
    assert (await server.backups.backup_health()).readiness == "attention"


async def test_periodic_drill_is_bounded_and_failure_details_are_private(
    populated_server, monkeypatch
):
    server = populated_server
    snapshot = await server.backups.create_snapshot()
    plan = AsyncMock(side_effect=RuntimeError("secret-token-should-not-escape"))
    monkeypatch.setattr(server.backups, "plan_restore", plan)
    assert await maintain_assurance(server.backups)
    assert plan.call_count == 1
    assert not await maintain_assurance(server.backups)
    health = await server.backups.backup_health()
    assert health.drill["status"] == "failed"
    assert "secret-token-should-not-escape" not in health.model_dump_json()
    assert snapshot.backup_id == health.recovery_backup_id


async def test_restore_review_can_repair_invalid_player_configuration(populated_server):
    server = populated_server
    snapshot = await server.backups.create_snapshot()
    path = Path(server.paths.server_dir) / "permissions.json"
    path.write_text("invalid-secret-value")
    plan = await server.backups.plan_restore(snapshot.backup_id, ["permissions.json"])
    assert plan.setting_changes[0].before == "Invalid current JSON (values hidden)"
    assert "invalid-secret-value" not in plan.model_dump_json()
