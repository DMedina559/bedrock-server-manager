"""Verify observable behavior across persistence, task and transport boundaries."""

import asyncio
import time

import pytest

from bedrock_server_manager.diagnostics.history import DiagnosticHistoryStore
from bedrock_server_manager.diagnostics.models import (
    DiagnosticOptions,
    DiagnosticRecord,
    DiagnosticSection,
    PluginValues,
    RuntimeDiagnostics,
)
from bedrock_server_manager.diagnostics.service import Diagnostics
from bedrock_server_manager.error import OperationConflictError, UserInputError
from bedrock_server_manager.web.schemas import UserResponse
from bedrock_server_manager.web.websocket_manager import ConnectionManager


async def test_history_filters_and_keyset_pages_preserve_equal_timestamp_records(db):
    store = DiagnosticHistoryStore(db, DiagnosticOptions())
    store.start()
    sampled = time.time()
    for index in range(5):
        store.enqueue(
            DiagnosticRecord(
                id=f"{index:032x}",
                instance_id="a" * 32,
                timestamp=sampled,
                subsystem="events",
                operation="test_event",
                outcome="failed",
                owner="plugin:probe",
                code="event_listener_failed",
                operation_id=f"event:{index}",
                correlation_id="workflow",
            )
        )
    await store.queue.join()
    page = await store.read(
        limit=2, owner="plugin:probe", outcome="failed", code="event_listener_failed"
    )
    ids = []
    while True:
        ids.extend(record.id for record in page.records)
        if page.next_cursor is None:
            break
        page = await store.read(
            limit=2,
            owner="plugin:probe",
            outcome="failed",
            code="event_listener_failed",
            cursor=page.next_cursor,
        )
    assert ids == [f"{index:032x}" for index in reversed(range(5))]
    assert (await store.read(operation_id="event:3")).records[0].id == f"{3:032x}"
    with pytest.raises(UserInputError):
        await store.read(cursor="invalid cursor")
    runs = await store.runs(current_instance="a" * 32)
    assert runs.available and runs.runs[0].retained_records == 5
    assert runs.runs[0].failed_records == 5 and runs.runs[0].current_instance
    await store.close()


async def test_failed_provider_retains_last_observation_and_rejection_counts(db):
    options = DiagnosticOptions(max_providers_per_owner=1)
    service = Diagnostics(DiagnosticHistoryStore(db, options), options)
    failed = False

    async def provider():
        if failed:
            raise RuntimeError("token=PRIVATE")
        return PluginValues(
            health="ok", values={"pending": 2}, units={"pending": "count"}
        )

    service.register("plugin:probe:queue", provider, owner="plugin:probe")
    with pytest.raises(ValueError):
        service.register("plugin:probe:other", provider, owner="plugin:probe")
    first = await service.snapshot()
    failed = True
    second = await service.snapshot()
    assert first.sections[0].status == "ok"
    assert second.sections[0].status == "unavailable" and second.sections[0].stale
    assert second.sections[0].data.values["pending"] == 2
    stale_runtime = DiagnosticSection(
        name="runtime",
        collected_at=time.time(),
        status="unavailable",
        stale=True,
        data=RuntimeDiagnostics(
            phase="ready",
            ready=True,
            pid=1,
            uptime_seconds=1,
            version="test",
            python_version="test",
        ),
    )
    assert not service.summary([stale_runtime]).ready
    assert second.sections[0].last_success_at == first.sections[0].last_success_at
    assert second.registry.failures == 1 and second.registry.rejected == 1
    assert "PRIVATE" not in second.model_dump_json()
    await service.close()


async def test_managed_task_progress_and_events_share_real_correlation(app_context):
    manager = app_context.task_manager
    entered, release = asyncio.Event(), asyncio.Event()
    correlation = []

    async def operation():
        manager.report_progress(25, plugin_owner="probe")
        with pytest.raises(UserInputError):
            manager.report_progress(float("nan"), plugin_owner="probe")
        event = await app_context.events.emit("diagnostic_workflow", {}, public=False)
        correlation.append(event.correlation_id)
        entered.set()
        await release.wait()
        return {"done": True}

    task_id = await manager.run_task(operation, _plugin_owner="probe")
    try:
        await entered.wait()
        with pytest.raises(OperationConflictError):
            manager.report_progress(50, plugin_owner="probe")
        snapshot = manager.diagnostic_snapshot()
        task = next(item for item in snapshot.tasks if item.id == task_id)
        assert task.name == "operation" and task.progress_percent == 25
        assert task.correlation_id == correlation[0]
        trace = await app_context.diagnostics.trace(correlation[0])
        assert trace.tasks[0].id == task_id
        assert any(event.name == "diagnostic_workflow" for event in trace.events.recent)
        release.set()
        await manager.futures[task_id]
        for _ in range(30):
            if manager.diagnostic_snapshot().tasks[0].status == "completed":
                break
            await asyncio.sleep(0)
        assert manager.diagnostic_snapshot().tasks[0].progress_percent == 100
    finally:
        release.set()


async def test_websocket_queue_is_bounded_serial_and_counts_pressure():
    entered, release = asyncio.Event(), asyncio.Event()
    sent = []
    active = 0

    class Socket:
        async def send_text(self, text):
            nonlocal active
            active += 1
            assert active == 1
            entered.set()
            await release.wait()
            sent.append(text)
            active -= 1

        async def close(self, **kwargs):
            release.set()

    manager = ConnectionManager(outbound_queue_limit=2)
    user = UserResponse(id=1, username="private-user", role="admin", is_active=True)
    client_id = await manager.connect(Socket(), user)
    first = asyncio.create_task(manager.send_to_client({"index": 1}, client_id))
    await entered.wait()
    second = asyncio.create_task(manager.send_to_client({"index": 2}, client_id))
    await asyncio.sleep(0)
    rejected = await manager.send_to_client({"index": 3}, client_id)
    assert rejected.failed == 1
    pressure = manager.diagnostic_snapshot()
    assert pressure.pending_sends == 2 and pressure.active_sends == 1
    assert pressure.dropped_messages == 1
    assert "private-user" not in pressure.model_dump_json()
    release.set()
    assert (await first).sent == 1 and (await second).sent == 1
    assert len(sent) == 2 and manager.diagnostic_snapshot().pending_sends == 0
    await manager.shutdown()
    assert manager.diagnostic_snapshot().disconnects_by_reason["shutdown"] == 1


async def test_aggregate_reports_and_runs_remain_admin_only(
    admin_auth_client, auth_client
):
    assert (await auth_client.get("/api/diagnostics/runs")).status_code == 403
    assert (await auth_client.get("/api/diagnostics/trace/example")).status_code == 403
    report = await admin_auth_client.get("/api/diagnostics/report")
    assert report.status_code == 200
    assert report.headers["cache-control"] == "no-store"
    assert "attachment" in report.headers["content-disposition"]
    data = report.json()
    assert len(data["report_id"]) == 32 and data["runs"]["available"]
    assert data["snapshot"]["summary"]["ready"]
    assert data["snapshot"]["environment"]["database_dialect"] == "sqlite"
    assert "database_schema_revision" in data["snapshot"]["environment"]
    assert (
        await admin_auth_client.get("/api/diagnostics/history?cursor=invalid")
    ).status_code == 400
    assert (
        await admin_auth_client.get("/api/diagnostics/history?outcome=unknown")
    ).status_code == 422


async def test_storage_reload_failures_preserve_state_and_report_evidence(
    app_context, monkeypatch
):
    storage = app_context.storage
    initial = storage.diagnostic_snapshot()
    before = app_context.state.settings.to_dict()

    async def fail(state):
        raise RuntimeError("password=PRIVATE")

    with monkeypatch.context() as patch:
        patch.setattr(storage, "_load_state", fail)
        with pytest.raises(RuntimeError):
            await storage.load_state(app_context.state)
    assert app_context.state.settings.to_dict() == before
    failed = storage.diagnostic_snapshot()
    assert failed.reload_failures == initial.reload_failures + 1
    assert not failed.reload_active and failed.last_reload_error_type == "RuntimeError"
    assert "PRIVATE" not in failed.model_dump_json()
    await storage.load_state(app_context.state)
    recovered = storage.diagnostic_snapshot()
    assert recovered.last_reload_error_type is None
    assert recovered.reload_successes == initial.reload_successes + 1


async def test_metric_collection_failure_recovery_and_timing_are_observed(
    app_context, monkeypatch
):
    sampler = app_context.metrics_service
    initial = sampler.diagnostic_snapshot()

    def fail():
        raise RuntimeError("PRIVATE")

    with monkeypatch.context() as patch:
        patch.setattr(sampler, "_collect", fail)
        with pytest.raises(RuntimeError):
            await sampler.sample()
    failed = sampler.diagnostic_snapshot()
    assert failed.failures == initial.failures + 1
    assert failed.last_duration_ms >= 0 and failed.last_error_type == "RuntimeError"
    assert "PRIVATE" not in failed.model_dump_json()
    await sampler.sample()
    recovered = sampler.diagnostic_snapshot()
    assert recovered.successes == initial.successes + 1
    assert recovered.last_error_type is None and recovered.last_sample_at is not None


async def test_websocket_timeout_is_recorded_without_client_identifiers():
    class Socket:
        async def send_text(self, text):
            await asyncio.Event().wait()

    manager = ConnectionManager()
    manager.io_timeout = 0.01
    user = UserResponse(id=1, username="private-user", role="admin", is_active=True)
    client = await manager.connect(Socket(), user)
    result = await manager.send_to_client({"payload": "PRIVATE"}, client)
    assert result.failed == 1
    observed = manager.diagnostic_snapshot()
    assert observed.send_timeouts == 1 and observed.pending_sends == 0
    assert observed.disconnects_by_reason["send_timeout"] == 1
    assert "PRIVATE" not in observed.model_dump_json()


def test_history_index_migration_preserves_existing_records(tmp_path):
    from importlib.resources import files

    import sqlalchemy as sa
    from alembic import command
    from alembic.config import Config

    config = Config(str(files("bedrock_server_manager").joinpath("db/alembic.ini")))
    config.set_main_option("skip_logging_config", "true")
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'migration.db'}")
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "d1a602f43b71")
        table = sa.Table("diagnostic_history", sa.MetaData(), autoload_with=connection)
        record = DiagnosticRecord(
            id="b" * 32,
            instance_id="a" * 32,
            timestamp=time.time(),
            subsystem="tasks",
            operation="probe",
            owner="probe",
            outcome="failed",
            code="task_failed",
            operation_id="task:1",
        )
        connection.execute(
            table.insert().values(
                id=record.id,
                instance_id=record.instance_id,
                timestamp=record.timestamp,
                subsystem=record.subsystem,
                correlation_id=None,
                record=record.model_dump(mode="json"),
            )
        )
        command.upgrade(config, "head")
        upgraded = sa.Table(
            "diagnostic_history", sa.MetaData(), autoload_with=connection
        )
        row = connection.execute(sa.select(upgraded)).mappings().one()
        assert (row["owner"], row["code"], row["outcome"], row["operation_id"]) == (
            "probe",
            "task_failed",
            "failed",
            "task:1",
        )
        assert row["record"] == record.model_dump(mode="json")
        command.downgrade(config, "d1a602f43b71")
        restored = sa.Table(
            "diagnostic_history", sa.MetaData(), autoload_with=connection
        )
        assert connection.execute(
            sa.select(restored.c.record)
        ).scalar_one() == record.model_dump(mode="json")
    engine.dispose()
