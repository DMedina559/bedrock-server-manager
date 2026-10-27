"""Transactional scheduling under retries, contention, edits, and restarts."""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock

import pytest
from pydantic import BaseModel, Field

from bedrock_server_manager.api.models.scheduler import (
    ControlScheduleRequest,
)
from bedrock_server_manager.scheduler.engine import occurrences
from bedrock_server_manager.scheduler.runner import (
    DeferredRun,
    activation,
    run_schedule,
)
from bedrock_server_manager.state.settings import ScheduledTask

START = datetime(2026, 10, 26, 2, 59, tzinfo=timezone.utc)


async def setup_job(context, server, monkeypatch, **extra):
    service = context.scheduler
    config = ScheduledTask(
        task="verify",
        server_name=server.server_name,
        time="03:00",
        stagger_minutes=0,
        catch_up=False,
        **extra,
    ).model_dump()
    monkeypatch.setattr(
        service.repository, "_activation", lambda config: activation(config, START)
    )
    await service.repository.save("job", config)
    return service, config


async def test_retry_is_independent_from_catch_up_policy(
    app_context, populated_server, monkeypatch
):
    service, config = await setup_job(app_context, populated_server, monkeypatch)
    execute = AsyncMock(side_effect=[RuntimeError(), None])
    for seconds in (90, 211):
        await run_schedule(
            service.repository,
            "job",
            config,
            populated_server,
            execute,
            moment=START + timedelta(seconds=seconds),
        )
    assert execute.await_count == 2
    assert (await service.repository.state("job"))["status"] == "completed"


async def test_first_poll_after_due_time_uses_save_activation(
    app_context, populated_server, monkeypatch
):
    service, config = await setup_job(app_context, populated_server, monkeypatch)
    execute = AsyncMock()
    assert await run_schedule(
        service.repository,
        "job",
        config,
        populated_server,
        execute,
        moment=START + timedelta(seconds=65),
    )
    assert execute.await_count == 1


async def test_stale_definition_does_not_run_after_pause(
    app_context, populated_server, monkeypatch
):
    service, config = await setup_job(app_context, populated_server, monkeypatch)
    await service.repository.save("job", dict(config, enabled=False))
    execute = AsyncMock()
    assert not await run_schedule(
        service.repository,
        "job",
        config,
        populated_server,
        execute,
        moment=START + timedelta(minutes=2),
    )
    execute.assert_not_called()


async def test_concurrent_claims_execute_once(
    app_context, populated_server, monkeypatch
):
    service, config = await setup_job(app_context, populated_server, monkeypatch)
    entered, release = asyncio.Event(), asyncio.Event()

    async def execute(*args):
        entered.set()
        await release.wait()

    first = asyncio.create_task(
        run_schedule(
            service.repository,
            "job",
            config,
            populated_server,
            execute,
            moment=START + timedelta(minutes=2),
        )
    )
    await entered.wait()
    assert not await run_schedule(
        service.repository,
        "job",
        config,
        populated_server,
        AsyncMock(),
        moment=START + timedelta(minutes=2),
    )
    release.set()
    assert await first


async def test_deferral_does_not_consume_attempts(
    app_context, populated_server, monkeypatch
):
    service, config = await setup_job(app_context, populated_server, monkeypatch)
    execute = AsyncMock(side_effect=DeferredRun())
    await run_schedule(
        service.repository,
        "job",
        config,
        populated_server,
        execute,
        moment=START + timedelta(minutes=2),
    )
    state = await service.repository.state("job")
    assert state["status"] == "deferred" and state["attempts"] == 0


async def test_plugin_job_ignores_broken_backup_catalog_and_validates_options(
    app_context, populated_server, monkeypatch
):
    class Options(BaseModel):
        count: int = Field(default=1, ge=1)

    bus = app_context.events
    bus.activate_owner("plugin:example")
    handler = AsyncMock()
    app_context.scheduler.register(
        "example:job",
        handler,
        owner="plugin:example",
        generation=bus.owner_generation("plugin:example"),
        options_model=Options,
        with_context=True,
        requires_server_lock=False,
    )
    monkeypatch.setattr(
        populated_server.backups.catalog,
        "load",
        Mock(side_effect=AssertionError("No backup catalog")),
    )
    await app_context.scheduler._execute(
        {"task": "example:job", "options": {"count": 2}},
        populated_server,
        "stable-slot",
        execution={"attempts": 2},
    )
    assert (
        handler.await_args.kwargs["execution_context"]["idempotency_key"]
        == "stable-slot"
    )
    assert handler.await_args.kwargs["execution_context"]["attempt"] == 2


async def test_controls_reject_stale_revision_and_queue_manual_run(
    app_context, populated_server, monkeypatch
):
    from bedrock_server_manager.error import UserInputError

    service, config = await setup_job(app_context, populated_server, monkeypatch)
    with pytest.raises(UserInputError):
        await service.control(
            ControlScheduleRequest(schedule_id="job", action="pause", revision="stale")
        )
    await service.control(ControlScheduleRequest(schedule_id="job", action="run_now"))
    assert (await service.repository.state("job"))["requested_slot"].startswith(
        "manual:"
    )


async def test_completed_attempt_reconciles_before_replaying_effect(
    app_context, populated_server, monkeypatch
):
    service, config = await setup_job(app_context, populated_server, monkeypatch)
    from bedrock_server_manager.scheduler.engine import signature

    slot = (
        "schedule:job:"
        + signature(config)
        + ":"
        + (START + timedelta(minutes=1)).isoformat()
    )
    await service.repository.run("job", slot, run_id="a" * 32, status="completed")
    execute = AsyncMock()
    assert await run_schedule(
        service.repository,
        "job",
        config,
        populated_server,
        execute,
        moment=START + timedelta(minutes=2),
    )
    execute.assert_not_called()
    assert (await service.repository.state("job"))["status"] == "completed"


async def test_pause_during_execution_retains_new_cursor(
    app_context, populated_server, monkeypatch
):
    service, config = await setup_job(app_context, populated_server, monkeypatch)

    async def execute(*args):
        await service.repository.save("job", dict(config, enabled=False))

    await run_schedule(
        service.repository,
        "job",
        config,
        populated_server,
        execute,
        moment=START + timedelta(minutes=2),
    )
    state = await service.repository.state("job")
    assert state["status"] == "disabled" and "lease" not in state


@pytest.mark.parametrize(
    "day,time,hour", [("2026-03-08", "02:30", 10), ("2026-11-01", "01:30", 8)]
)
def test_dst_gap_and_fold_have_explicit_first_occurrence(day, time, hour):
    config = ScheduledTask(
        task="verify",
        server_name="test",
        timezone="America/Los_Angeles",
        time=time,
        stagger_minutes=0,
    ).model_dump()
    moment = datetime.fromisoformat(day + "T12:00:00+00:00")
    matches = [
        slot
        for slot in occurrences(config, "test", moment)
        if slot.date() == moment.date()
    ]
    assert len(matches) == 1 and matches[0].hour == hour and matches[0].minute == 30


async def test_equal_definitions_have_distinct_schedule_slots(
    app_context, populated_server, monkeypatch
):
    service, config = await setup_job(app_context, populated_server, monkeypatch)
    await service.repository.save("other", config)
    calls = []

    async def execute(slot, execution):
        calls.append(slot)

    for name in ("job", "other"):
        await run_schedule(
            service.repository,
            name,
            config,
            populated_server,
            execute,
            moment=START + timedelta(minutes=2),
        )
    assert len(calls) == len(set(calls)) == 2


async def test_plugin_timeout_releases_lock(app_context, populated_server):
    service = app_context.scheduler
    bus = app_context.events
    bus.activate_owner("plugin:timeout")

    async def handler(**kwargs):
        await asyncio.sleep(10)

    service.register(
        "timeout:job",
        handler,
        owner="plugin:timeout",
        generation=bus.owner_generation("plugin:timeout"),
        timeout_seconds=1,
    )
    with pytest.raises(TimeoutError):
        await service._execute(
            {"task": "timeout:job", "options": {}}, populated_server, "slot"
        )
    assert not populated_server.operation_lock.locked()


async def test_control_endpoint_is_admin_only_and_exposes_revision(
    admin_auth_client, auth_client, app_context, populated_server, monkeypatch
):
    service, config = await setup_job(app_context, populated_server, monkeypatch)
    path = "/api/scheduler/schedules/job/action"
    assert (await auth_client.post(path, json={"action": "pause"})).status_code == 403
    listed = (await admin_auth_client.get("/api/scheduler/schedules")).json()
    revision = listed["schedules"][0]["revision"]
    result = await admin_auth_client.post(
        path, json={"action": "pause", "revision": revision}
    )
    assert result.status_code == 200, result.text
    assert not (await service.configurations())["job"][0]["enabled"]


async def test_busy_first_attempt_obeys_misfire_policy(
    app_context, populated_server, monkeypatch
):
    service, config = await setup_job(app_context, populated_server, monkeypatch)
    execute = AsyncMock()
    async with populated_server.operation_lock:
        assert not await run_schedule(
            service.repository,
            "job",
            config,
            populated_server,
            execute,
            moment=START + timedelta(minutes=1),
        )
    assert not await run_schedule(
        service.repository,
        "job",
        config,
        populated_server,
        execute,
        moment=START + timedelta(minutes=10),
    )
    assert (await service.repository.state("job"))["status"] == "skipped"
    execute.assert_not_called()


async def test_missing_timezone_remains_visible_in_schedule_listing(
    app_context, populated_server, monkeypatch
):
    from zoneinfo import ZoneInfoNotFoundError

    import bedrock_server_manager.scheduler.service as module

    service, config = await setup_job(app_context, populated_server, monkeypatch)

    def missing(*args):
        raise ZoneInfoNotFoundError("UTC")

    monkeypatch.setattr(module, "occurrences", missing)
    listed = await service.snapshot()
    assert listed.schedules[0].configuration.timezone == "UTC"
    assert not listed.schedules[0].available


async def test_manual_run_does_not_replay_completed_calendar_slot(
    app_context, populated_server, monkeypatch
):
    service, config = await setup_job(app_context, populated_server, monkeypatch)
    execute = AsyncMock()
    for minute in (1,):
        await run_schedule(
            service.repository,
            "job",
            config,
            populated_server,
            execute,
            moment=START + timedelta(minutes=minute),
        )
    await service.control(ControlScheduleRequest(schedule_id="job", action="run_now"))
    await run_schedule(
        service.repository,
        "job",
        config,
        populated_server,
        execute,
        moment=START + timedelta(minutes=2),
    )
    assert not await run_schedule(
        service.repository,
        "job",
        config,
        populated_server,
        execute,
        moment=START + timedelta(minutes=3),
    )
    assert execute.await_count == 2


async def test_intentionally_skipped_run_does_not_count_as_failure(
    app_context, populated_server, monkeypatch
):
    service, config = await setup_job(app_context, populated_server, monkeypatch)
    await service.repository.state(
        "job", {"status": "skipped", "blocked_reason": "missed_occurrence"}
    )
    assert (await service.diagnostic_snapshot()).values["failed"] == 0


@pytest.mark.parametrize("catch_up,expected", [(True, True), (False, False)])
def test_forecast_includes_eligible_catch_up_before_first_claim(catch_up, expected):
    from bedrock_server_manager.scheduler.runner import next_attempt

    config = ScheduledTask(
        task="verify",
        server_name="test",
        time="03:00",
        timezone="UTC",
        stagger_minutes=0,
        catch_up=catch_up,
    ).model_dump()
    record = activation(config, START)
    assert (
        bool(next_attempt(config, record, START + timedelta(hours=1), "job"))
        is expected
    )
