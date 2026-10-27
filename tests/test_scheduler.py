"""Database scheduling, opt-in verification and compatible legacy migration."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from bedrock_server_manager.api.models.scheduler import SaveScheduleRequest
from bedrock_server_manager.scheduler.engine import run_due
from bedrock_server_manager.state.settings import BackupSettings, ScheduledTask


def test_verification_is_opt_in():
    settings = BackupSettings()
    assert not settings.verify_after_create
    assert settings.verification_interval_hours == 0
    assert settings.recovery_drill_interval_hours == 0
    assert (
        BackupSettings(verification_interval_hours=168).verification_interval_hours
        == 168
    )


async def test_capture_does_not_unpack_until_requested(populated_server, monkeypatch):
    backups = populated_server.backups
    original = backups.unpack_snapshot
    # unpack_snapshot is a synchronous worker callable.
    from unittest.mock import Mock

    unpack = Mock(wraps=original)
    monkeypatch.setattr(backups, "unpack_snapshot", unpack)
    snapshot = await backups.create_snapshot()
    assert snapshot.verification.status == "unverified"
    unpack.assert_not_called()
    await populated_server.settings.set("backups.verify_after_create", True)
    verified = await backups.create_snapshot()
    assert verified.verification.status == "verified"
    assert unpack.call_count == 1


async def test_scheduler_persists_runs_and_restarts(
    app_context, populated_server, monkeypatch
):
    service = app_context.scheduler
    from bedrock_server_manager.scheduler.runner import activation

    moment = datetime(2026, 1, 1, 2, tzinfo=timezone.utc)
    monkeypatch.setattr(
        service.repository, "_activation", lambda config: activation(config, moment)
    )
    config = ScheduledTask(
        task="verify",
        server_name=populated_server.server_name,
        time="03:00",
        stagger_minutes=0,
    )
    await service.save(
        SaveScheduleRequest(schedule_id="weekly-check", configuration=config)
    )
    rows = (await service.snapshot()).schedules
    assert len(rows) == 1 and rows[0].available
    assert rows[0].configuration.task == "verify"
    moment = datetime(2026, 1, 1, 2, tzinfo=timezone.utc)

    async def read():
        return await service.repository.state("weekly-check")

    async def write(value):
        await service.repository.state("weekly-check", value)

    async def capture(slot):
        await service.execute(
            "weekly-check", config.model_dump(), populated_server, slot
        )

    assert not await run_due(
        populated_server.backups,
        moment,
        config=config.model_dump(),
        read_state=read,
        write_state=write,
        capture=capture,
    )
    assert await run_due(
        populated_server.backups,
        moment + timedelta(hours=1),
        config=config.model_dump(),
        read_state=read,
        write_state=write,
        capture=capture,
    )
    assert not await run_due(
        populated_server.backups,
        moment + timedelta(hours=2),
        config=config.model_dump(),
        read_state=read,
        write_state=write,
        capture=capture,
    )
    runs = await service.repository.history("weekly-check")
    assert runs[0]["status"] == "completed" and runs[0]["correlation_id"]
    from bedrock_server_manager.scheduler.service import Scheduler

    restarted = Scheduler(app_context)
    assert (await restarted.snapshot()).schedules[0].last_status == "completed"


async def test_legacy_schedules_are_imported_once_and_remain_editable(
    app_context, populated_server
):
    name = populated_server.server_name
    await app_context.settings.set("backups.schedules", {name: {"time": "04:00"}})
    service = app_context.scheduler
    first = (await service.snapshot()).schedules
    second = (await service.snapshot()).schedules
    assert len(first) == len(second) == 1
    assert first[0].schedule_id == second[0].schedule_id and first[0].legacy
    await app_context.settings.set("backups.schedules", {name: {"time": "05:00"}})
    assert (await service.snapshot()).schedules[0].configuration.time == "05:00"
    await service.delete(first[0].schedule_id)
    assert not (await service.snapshot()).schedules


async def test_scheduler_endpoints_are_admin_only(
    admin_auth_client, auth_client, unauth_client, populated_server
):
    path = "/api/scheduler/schedules"
    assert (await unauth_client.get(path)).status_code == 401
    assert (await auth_client.get(path)).status_code == 403
    config = {
        "task": "verify",
        "server_name": populated_server.server_name,
        "enabled": False,
    }
    result = await admin_auth_client.put(path + "/weekly", json=config)
    assert result.status_code == 200, result.text
    result = await admin_auth_client.get(path)
    assert result.status_code == 200, result.text
    assert result.headers["cache-control"] == "no-store"
    assert result.json()["schedules"][0]["configuration"]["task"] == "verify"
    assert (await admin_auth_client.delete(path + "/weekly")).status_code == 200


async def test_plugin_registration_is_namespaced_and_revoked(
    app_context, populated_server
):
    service = app_context.scheduler
    bus = app_context.events
    bus.activate_owner("plugin:example")
    callback = AsyncMock()
    with pytest.raises(ValueError):
        service.register(
            "other:task",
            callback,
            owner="plugin:example",
            generation=bus.owner_generation("plugin:example"),
        )
    service.register(
        "example:task",
        callback,
        owner="plugin:example",
        generation=bus.owner_generation("plugin:example"),
    )
    assert service.available("example:task")
    await service._execute(
        {"task": "example:task", "options": {"x": 1}}, populated_server, "slot"
    )
    callback.assert_awaited_once_with(
        server_name=populated_server.server_name, options={"x": 1}
    )
    bus.remove_owner("plugin:example")
    assert not service.available("example:task")


async def test_scheduler_shutdown_recovers_interrupted_attempts(
    app_context, populated_server
):
    service = app_context.scheduler
    config = ScheduledTask(task="backup", server_name=populated_server.server_name)
    await service.save(SaveScheduleRequest(schedule_id="nightly", configuration=config))
    await service.repository.state("nightly", {"status": "running", "attempts": 1})
    await service.repository.run("nightly", "slot", run_id="a" * 32, status="running")
    await service.repository.recover()
    assert (await service.repository.state("nightly"))["status"] == "interrupted"
    assert (await service.repository.history("nightly"))[0]["status"] == "interrupted"


async def test_restore_validation_is_mandatory_for_unverified_archives(
    populated_server,
):
    server = populated_server
    snapshot = await server.backups.create_snapshot()
    assert snapshot.verification.status == "unverified"
    path = server.backups.resolve_backup(snapshot.backup_id)
    path.write_bytes(b"damaged archive")
    from bedrock_server_manager.error import BackupRestoreError

    with pytest.raises(BackupRestoreError):
        await server.backups.plan_restore(snapshot.backup_id, ["world"])


async def test_delete_respects_pins_and_removes_only_local_archive(populated_server):
    from bedrock_server_manager.error import BackupRestoreError

    backups = populated_server.backups
    snapshot = await backups.create_snapshot()
    await backups.pin_snapshot(snapshot.backup_id, True)
    with pytest.raises(BackupRestoreError):
        await backups.delete_snapshot(snapshot.backup_id)
    await backups.pin_snapshot(snapshot.backup_id, False)
    await backups.delete_snapshot(snapshot.backup_id)
    assert not await backups.list_snapshots()


async def test_same_sequence_reuses_complete_unverified_capture(populated_server):
    server = populated_server
    with server.operations.scope("workflow", server_name=server.server_name):
        capture = await server.backups.create_snapshot()
        assert capture.verification.status == "unverified"
        assert await server.backups.can_reuse_sequence_snapshot()
    assert not await server.backups.can_reuse_sequence_snapshot()


async def test_run_history_is_bounded(app_context, populated_server):
    service = app_context.scheduler
    await service.save(
        SaveScheduleRequest(
            schedule_id="bounded",
            configuration=ScheduledTask(
                task="verify", server_name=populated_server.server_name
            ),
        )
    )
    for index in range(105):
        await service.repository.run(
            "bounded", "slot", run_id=f"{index:032d}", status="completed"
        )
    assert len(await service.repository.history("bounded", 200)) == 100
    assert len((await service.snapshot()).schedules[0].runs) == 20


async def test_verification_job_continues_after_a_corrupt_archive(
    app_context, populated_server, monkeypatch
):
    from types import SimpleNamespace

    backups = populated_server.backups
    listed = [
        SimpleNamespace(
            backup_id=name,
            verification=SimpleNamespace(
                status="failed", verified_at=datetime.now(timezone.utc).isoformat()
            ),
        )
        for name in ("bad", "good")
    ]
    monkeypatch.setattr(backups, "list_snapshots", AsyncMock(return_value=listed))
    verify = AsyncMock(side_effect=[RuntimeError("private failure"), None])
    monkeypatch.setattr(backups, "verify_snapshot", verify)
    with pytest.raises(RuntimeError, match="Some scheduled"):
        await app_context.scheduler._execute(
            {"task": "verify", "options": {}}, populated_server, "slot"
        )
    assert verify.await_count == 2


async def test_save_complete_browser_backup_schedule(
    admin_auth_client, populated_server
):
    response = await admin_auth_client.put(
        "/api/scheduler/schedules/backup-test",
        json={
            "task": "backup",
            "server_name": populated_server.server_name,
            "enabled": True,
            "time": "03:00",
            "timezone": "UTC",
            "weekdays": [0, 1, 2, 3, 4, 5, 6],
            "catch_up": False,
            "stagger_minutes": 15,
            "options": {},
        },
    )
    assert response.status_code == 200, response.text


@pytest.mark.parametrize("zone", ["UTC", "Etc/UTC"])
async def test_browser_schedule_works_without_iana_database(
    admin_auth_client, populated_server, monkeypatch, zone
):
    from zoneinfo import ZoneInfoNotFoundError

    from bedrock_server_manager.scheduler.engine import occurrences
    from bedrock_server_manager.utils import timezones

    def unavailable(name):
        raise ZoneInfoNotFoundError(name)

    monkeypatch.setattr(timezones, "ZoneInfo", unavailable)
    payload = {
        "task": "backup",
        "server_name": populated_server.server_name,
        "enabled": False,
        "time": "03:00",
        "timezone": zone,
        "weekdays": [0, 1, 2, 3, 4, 5, 6],
        "catch_up": False,
        "stagger_minutes": 15,
        "options": {},
    }
    response = await admin_auth_client.put(
        "/api/scheduler/schedules/backup-test", json=payload
    )
    assert response.status_code == 200, response.text
    moment = datetime(2026, 10, 26, tzinfo=timezone.utc)
    assert occurrences(payload, populated_server.server_name, moment)
    listed = await admin_auth_client.get("/api/scheduler/schedules")
    assert listed.status_code == 200, listed.text
    assert listed.json()["schedules"][0]["configuration"]["timezone"] == zone
    from bedrock_server_manager.state.settings import BackupSchedule

    with pytest.raises(ValueError):
        BackupSchedule(timezone="Invalid/Region")


async def test_scheduler_writes_publish_committed_state_and_storage_metrics(
    app_context, populated_server
):
    service = app_context.scheduler
    observed = []
    app_context.storage.subscribe(
        lambda state, changes: observed.append(changes.schedules_changed)
    )
    before = app_context.storage.diagnostic_snapshot().successes
    await service.save(
        SaveScheduleRequest(
            schedule_id="state-test",
            configuration=ScheduledTask(
                task="backup", server_name=populated_server.server_name
            ),
        )
    )
    assert app_context.state.scheduler.count == 1
    assert app_context.storage.diagnostic_snapshot().successes > before
    assert {"state-test"} in observed
    copied = app_context.state.scheduler.records
    copied["state-test"][0]["task"] = "verify"
    assert app_context.state.scheduler.records["state-test"][0]["task"] == "backup"
    await service.delete("state-test")
    assert app_context.state.scheduler.count == 0


async def test_scheduler_rollback_keeps_committed_state(
    app_context, populated_server, monkeypatch
):
    from unittest.mock import AsyncMock

    from sqlalchemy.ext.asyncio import AsyncSession

    from bedrock_server_manager.error import StorageError

    service = app_context.scheduler
    before = app_context.state.scheduler.records
    with monkeypatch.context() as patch:
        patch.setattr(
            AsyncSession, "commit", AsyncMock(side_effect=OSError("private db failure"))
        )
        with pytest.raises(StorageError):
            await service.save(
                SaveScheduleRequest(
                    schedule_id="failed",
                    configuration=ScheduledTask(
                        task="backup", server_name=populated_server.server_name
                    ),
                )
            )
    assert app_context.state.scheduler.records == before
    assert app_context.storage.diagnostic_snapshot().failures > 0


async def test_scheduler_diagnostics_are_side_effect_free_and_report_loop(
    app_context, populated_server, monkeypatch
):
    from bedrock_server_manager.diagnostics.health import evaluate_health
    from bedrock_server_manager.diagnostics.models import DiagnosticOptions

    service = app_context.scheduler
    monkeypatch.setattr(
        service,
        "snapshot",
        AsyncMock(
            side_effect=AssertionError(
                "Diagnostics must not migrate or query schedule history"
            )
        ),
    )
    data = await service.diagnostic_snapshot()
    assert data.kind == "plugin_values" and not data.values["running"]
    assert evaluate_health(data, DiagnosticOptions())[0] == "degraded"
    assert not service.check_health()


def test_pacific_schedule_observes_daylight_saving():
    from bedrock_server_manager.scheduler.engine import occurrences

    config = ScheduledTask(
        task="backup",
        server_name="test",
        time="14:42",
        timezone="America/Los_Angeles",
        stagger_minutes=0,
    ).model_dump()
    winter = datetime(2026, 1, 1, tzinfo=timezone.utc)
    summer = datetime(2026, 7, 1, tzinfo=timezone.utc)
    assert {slot.hour for slot in occurrences(config, "test", winter)} == {22}
    assert {slot.hour for slot in occurrences(config, "test", summer)} == {21}


def test_named_timezone_uses_portable_tzdata_when_system_lookup_fails(monkeypatch):
    from zoneinfo import ZoneInfoNotFoundError

    from bedrock_server_manager.utils import timezones

    def missing(name):
        raise ZoneInfoNotFoundError(name)

    monkeypatch.setattr(timezones, "ZoneInfo", missing)
    timezones.resolve_timezone.cache_clear()
    zone = timezones.resolve_timezone("America/Los_Angeles")
    assert datetime(2026, 1, 1, tzinfo=zone).utcoffset() == timedelta(hours=-8)
    assert datetime(2026, 7, 1, tzinfo=zone).utcoffset() == timedelta(hours=-7)


async def test_diagnostic_history_links_scheduled_runs(
    app_context, populated_server, monkeypatch
):
    service = app_context.scheduler
    config = ScheduledTask(task="verify", server_name=populated_server.server_name)
    await service.save(
        SaveScheduleRequest(schedule_id="trace-job", configuration=config)
    )
    from unittest.mock import Mock

    diagnostics = app_context.diagnostics
    record = Mock(wraps=diagnostics.record)
    monkeypatch.setattr(diagnostics, "record", record)
    await service.execute("trace-job", config.model_dump(), populated_server, "slot")
    # Recorder metadata is bound to the same operation correlation as run history.
    runs = await service.repository.history("trace-job")
    assert runs[0]["correlation_id"]
    call = next(call for call in record.call_args_list if call.args[0] == "scheduler")
    assert call.kwargs["correlation_id"] == runs[0]["correlation_id"]
    assert call.kwargs["operation_id"]
    assert app_context.state.scheduler.records["trace-job"][0]["task"] == "verify"


async def test_new_schedules_inherit_application_timezone_without_moving_saved_jobs(
    app_context, populated_server
):
    service = app_context.scheduler
    await app_context.settings.set("general.timezone", "America/Los_Angeles")
    await app_context.reload()
    assert app_context.settings.get("general.timezone") == "America/Los_Angeles"

    def request(name, **extra):
        return SaveScheduleRequest(
            schedule_id=name,
            configuration=ScheduledTask(
                task="backup", server_name=populated_server.server_name, **extra
            ),
        )

    await service.save(request("local"))
    await service.save(request("explicit", timezone="UTC"))
    await app_context.settings.set("general.timezone", "America/New_York")
    await service.save(request("local", time="04:00"))
    rows = {name: config for name, config, *_ in await service.repository.list()}
    assert rows["local"]["timezone"] == "America/Los_Angeles"
    assert rows["local"]["time"] == "04:00"
    assert rows["explicit"]["timezone"] == "UTC"
    await service.save(request("new"))
    assert (await service.configurations())["new"][0]["timezone"] == "America/New_York"
