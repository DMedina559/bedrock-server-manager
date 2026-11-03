"""Exercise diagnostics against real persistence and application routes."""

import asyncio
import time

import pytest

from bedrock_server_manager.diagnostics.history import DiagnosticHistoryStore
from bedrock_server_manager.diagnostics.models import DiagnosticOptions, PluginValues
from bedrock_server_manager.diagnostics.service import Diagnostics


@pytest.mark.asyncio
async def test_history_survives_restart_and_retains_only_bounded_metadata(db):
    options = DiagnosticOptions(history_limit=2)
    history = DiagnosticHistoryStore(db, options)
    service = Diagnostics(history, options)
    history.start()
    for index in range(3):
        service.record(
            "storage",
            "transaction",
            started=time.monotonic(),
            error=RuntimeError("password=SECRET"),
        )
    await history.queue.join()
    previous_instance = service.instance_id
    await service.close()
    restarted = DiagnosticHistoryStore(db, options)
    result = await restarted.read(instance_id=previous_instance)
    assert result.available and len(result.records) == 2
    assert all(record.instance_id == previous_instance for record in result.records)
    assert "SECRET" not in result.model_dump_json()
    assert any(record.error_type == "RuntimeError" for record in result.records)
    await restarted.close()


@pytest.mark.asyncio
async def test_slow_and_broken_plugin_providers_do_not_hide_other_sections(db):
    options = DiagnosticOptions(provider_timeout_seconds=0.01)
    service = Diagnostics(DiagnosticHistoryStore(db, options), options)
    service.start()
    calls = 0
    release = asyncio.Event()

    async def slow():
        nonlocal calls
        calls += 1
        while not release.is_set():
            try:
                await release.wait()
            except asyncio.CancelledError:
                pass
        return PluginValues(values={"queued": 1})

    async def healthy():
        return PluginValues(values={"queued": 2})

    async def broken():
        raise RuntimeError("SECRET")

    service.register("plugin:demo:slow", slow, owner="plugin:demo")
    service.register("plugin:other:healthy", healthy, owner="plugin:other")
    service.register("plugin:other:broken", broken, owner="plugin:other")
    try:
        for _ in range(2):
            result = await service.snapshot()
            sections = {section.name: section for section in result.sections}
            assert sections["plugin:demo:slow"].status == "unavailable"
            assert sections["plugin:other:healthy"].data.values["queued"] == 2
            assert sections["plugin:other:broken"].status == "unavailable"
            assert "SECRET" not in result.model_dump_json()
        assert calls == 1
        assert service.provider_timeouts == 1
        await service.history.queue.join()
        timeout_records = await service.history.read(code="provider_timeout")
        assert len(timeout_records.records) == 1
        service.remove_owner("plugin:demo")
        with pytest.raises(ValueError, match="draining"):
            service.register("plugin:demo:slow", healthy, owner="plugin:demo")
        with pytest.raises(ValueError, match="owner"):
            service.register("plugin:other:stolen", healthy, owner="plugin:demo")
    finally:
        release.set()
        await asyncio.sleep(0)
        await service.close()


@pytest.mark.asyncio
async def test_database_failure_does_not_break_recording_or_collection(db, monkeypatch):
    options = DiagnosticOptions(queue_limit=1)
    store = DiagnosticHistoryStore(db, options)
    service = Diagnostics(store, options)
    service.record("storage", "transaction", started=time.monotonic())
    service.record("storage", "transaction", started=time.monotonic())
    assert store.dropped == 1

    async def fail(record):
        raise RuntimeError("SECRET")

    monkeypatch.setattr(store, "_write", fail)
    store.start()
    await store.queue.join()
    assert (await service.snapshot()).persistence.write_failures == 1
    assert store.dropped == 2
    observation = (await service.snapshot()).persistence
    assert observation.last_error_type == "RuntimeError"
    assert (await service.snapshot()).collection.status == "degraded"
    await service.close()


@pytest.mark.asyncio
async def test_diagnostics_routes_require_admin_and_publish_typed_sections(
    admin_auth_client,
    auth_client,
    unauth_client,
    app_context,
):
    assert (await unauth_client.get("/api/diagnostics")).status_code == 401
    assert (await auth_client.get("/api/diagnostics")).status_code == 403
    result = await admin_auth_client.get("/api/diagnostics")
    assert result.status_code == 200
    data = result.json()
    sections = {section["name"]: section for section in data["sections"]}
    assert {
        "runtime",
        "events",
        "storage",
        "state",
        "transport",
        "plugins",
        "tasks",
        "metrics",
        "processes",
    } <= sections.keys()
    assert sections["state"]["data"]["kind"] == "state"
    assert "total_cpu_percent" in sections["processes"]["data"]
    assert "total_memory_mb" in sections["processes"]["data"]
    assert "unhealthy_count" in sections["processes"]["data"]
    assert "untracked_recoveries_count" in sections["processes"]["data"]
    assert data["counter_scope"] == "current_instance"
    assert (await admin_auth_client.get("/api/diagnostics/unknown")).status_code == 404
    assert (
        await admin_auth_client.get("/api/diagnostics/history?limit=201")
    ).status_code == 422
    report = await admin_auth_client.get("/api/diagnostics/report")
    assert report.status_code == 200 and report.json()["history"]["available"]
    assert "hashed_password" not in report.text
    assert not any("username" in section for section in sections)


@pytest.mark.asyncio
async def test_plugin_provider_and_typed_api_follow_real_load_unload(
    plugin_factory, app_context
):
    plugin = await plugin_factory(
        "diagnostic_probe",
        """
from bedrock_server_manager.plugins import PluginBase
from bedrock_server_manager.diagnostics import PluginValues

class Probe(PluginBase):
    name = "Diagnostic probe"
    version = "1.0"
    async def on_load(self):
        await self.api.runtime.register_diagnostic_provider("queue", self.observe)
    async def observe(self):
        return PluginValues(values={"pending": 3})
""",
    )
    snapshot = await plugin.api.diagnostics.get_application_diagnostics(
        {"subsystem": "plugin:diagnostic_probe:queue"}
    )
    assert snapshot.sections[0].owner == "plugin:diagnostic_probe"
    assert snapshot.sections[0].data.values["pending"] == 3

    # Full diagnostic snapshot should not mark active loaded plugin as draining
    full_snapshot = await app_context.diagnostics.snapshot()
    plugins_section = next(s for s in full_snapshot.sections if s.name == "plugins")
    probe_diag = next(
        p for p in plugins_section.data.plugins if p.name == "diagnostic_probe"
    )
    assert probe_diag.draining is False
    assert plugins_section.status == "ok"

    assert await app_context.plugin_manager.unload_plugin_by_name("diagnostic_probe")
    assert not (
        await app_context.diagnostics.snapshot("plugin:diagnostic_probe:queue")
    ).sections
    report = await app_context.api.diagnostics.get_diagnostic_report({})
    assert report.snapshot.instance_id == app_context.diagnostics.instance_id


@pytest.mark.asyncio
async def test_domain_transaction_failure_is_recorded_without_leaking_details(
    app_context,
):
    from bedrock_server_manager.error import StorageError

    service = app_context.diagnostics
    service.history.start()
    with pytest.raises(StorageError):
        async with app_context.storage.transaction():
            raise RuntimeError("secret=PRIVATE")
    await service.history.queue.join()
    history = await service.history.read(subsystem="storage")
    assert history.available and len(history.records) == 1
    assert history.records[0].outcome == "failed"
    assert "PRIVATE" not in history.model_dump_json()
    snapshot = await service.snapshot("storage")
    assert snapshot.sections[0].status == "degraded"
    assert snapshot.sections[0].data.active == 0


@pytest.mark.asyncio
async def test_event_failure_history_preserves_correlation_without_payload(app_context):
    service = app_context.diagnostics
    service.history.start()

    async def failed_observer(envelope):
        raise TimeoutError("password=PRIVATE")

    app_context.events.subscribe("diagnostic_probe", failed_observer, observer=True)
    receipt = await app_context.events.emit(
        "diagnostic_probe", {"secret": "PRIVATE"}, public=True
    )
    assert receipt.status == "partial"
    await service.history.queue.join()
    history = await service.history.read(correlation_id=receipt.correlation_id)
    assert history.available and history.records
    assert history.records[0].error_type == "TimeoutError"
    assert "PRIVATE" not in history.model_dump_json()
    assert "secret" not in history.model_dump_json()


@pytest.mark.asyncio
async def test_transient_failure_has_finite_attempts_and_one_drop(db, monkeypatch):
    store = DiagnosticHistoryStore(db, DiagnosticOptions())
    service = Diagnostics(store, store.options)
    calls = 0

    async def fail(record):
        nonlocal calls
        calls += 1
        raise TimeoutError

    monkeypatch.setattr(store, "_write", fail)
    store.start()
    try:
        service.record("storage", "bounded-retry", started=time.monotonic())
        await asyncio.wait_for(store.queue.join(), 5)
        assert calls == 3 and store.write_failures == 3
        assert store.dropped == 1 and store.last_error_type == "TimeoutError"
    finally:
        await store.close()


def test_retry_classification_distinguishes_locks_from_invalid_sql():
    import sqlite3

    from sqlalchemy.exc import OperationalError

    from bedrock_server_manager.diagnostics import history as module

    busy = sqlite3.OperationalError("busy")
    busy.sqlite_errorcode = sqlite3.SQLITE_BUSY
    assert module.retryable_write(OperationalError("query", {}, busy))
    invalid = sqlite3.OperationalError("no such table")
    invalid.sqlite_errorcode = sqlite3.SQLITE_ERROR
    assert not module.retryable_write(OperationalError("query", {}, invalid))
    assert not module.retryable_write(RuntimeError("invalid record"))


@pytest.mark.asyncio
async def test_processes_diagnostics_metrics_and_unhealthy_tracking(app_context):
    await app_context.server_service.register_or_update_server(
        "proc_diag_test",
        installed_version="1.21.0.0",
        status="RUNNING",
        target_version="LATEST",
    )
    app_context.state.runtime.update_server_runtime(
        "proc_diag_test",
        running=True,
        pid=12345,
        cpu_percent=12.5,
        memory_mb=256.0,
        recovered_untracked=True,
        process_observed_at=time.time(),
    )
    snapshot = await app_context.diagnostics.snapshot("processes")
    assert len(snapshot.sections) == 1
    assert snapshot.sections[0].status == "degraded"
    assert any(
        issue.code == "process_command_unavailable"
        for issue in snapshot.sections[0].issues
    )
    proc_diag = snapshot.sections[0].data
    assert proc_diag.total_cpu_percent == 12.5
    assert proc_diag.total_memory_mb == 256.0
    assert proc_diag.untracked_recoveries_count == 1
    assert proc_diag.unhealthy_count >= 1

    entry = next(p for p in proc_diag.processes if p.server_name == "proc_diag_test")
    assert entry.cpu_percent == 12.5
    assert entry.memory_mb == 256.0
    assert entry.recovered_untracked is True
    assert entry.healthy is False
    # When recovered process flag is cleared and process matches expected stopped state
    app_context.state.runtime.update_server_runtime(
        "proc_diag_test", running=False, pid=None
    )
    await app_context.server_service.register_or_update_server(
        "proc_diag_test",
        installed_version="1.21.0.0",
        status="STOPPED",
        target_version="LATEST",
    )
    clean_snapshot = await app_context.diagnostics.snapshot("processes")
    assert clean_snapshot.sections[0].status == "ok"


async def test_process_totals_include_rows_beyond_detail_limit(app_context):
    from bedrock_server_manager.state.models import ServerConfigState

    for index in range(101):
        name = f"summary_{index:03}"
        app_context.state.servers.set(
            ServerConfigState(server_name=name, status="RUNNING")
        )
        app_context.state.runtime.update_server_runtime(
            name,
            running=True,
            pid=index + 1,
            command_available=True,
            process_owned=True,
            output_source="file",
            process_observed_at=time.time(),
            cpu_percent=1,
            memory_mb=2,
        )
    # The unhealthy survivor lies beyond the 100 detailed entries.
    app_context.state.runtime.update_server_runtime(
        "summary_100",
        command_available=False,
        process_owned=False,
        recovered_untracked=True,
        output_source="unknown",
    )
    snapshot = await app_context.diagnostics.snapshot("processes")
    data = snapshot.sections[0].data
    assert len(data.processes) == 100 and data.truncated
    assert data.total_cpu_percent == 101
    assert data.total_memory_mb == 202
    assert data.untracked_recoveries_count == 1
    assert data.command_unavailable_count == 1
    assert data.unhealthy_count == 1
    assert snapshot.sections[0].status == "degraded"


def test_tasks_health_rule_evaluations():
    from bedrock_server_manager.diagnostics.health import evaluate_health
    from bedrock_server_manager.diagnostics.models import (
        DiagnosticOptions,
        TasksDiagnostics,
    )

    options = DiagnosticOptions()

    healthy_tasks = TasksDiagnostics(
        active=2,
        capacity=10,
        concurrency_limit=5,
        accepting=True,
        counts_by_status={"running": 2},
    )
    status, issues = evaluate_health(healthy_tasks, options)
    assert status == "ok"
    assert issues == []

    not_accepting = TasksDiagnostics(
        active=0,
        capacity=10,
        accepting=False,
        counts_by_status={},
    )
    status, issues = evaluate_health(not_accepting, options)
    assert status == "degraded"
    assert any(i.code == "tasks_not_accepting" for i in issues)

    at_capacity = TasksDiagnostics(
        active=5,
        capacity=10,
        concurrency_limit=5,
        accepting=True,
        counts_by_status={"running": 5},
    )
    status, issues = evaluate_health(at_capacity, options)
    assert status == "degraded"
    assert any(i.code == "task_capacity_reached" for i in issues)


def test_backups_health_rule_evaluations():
    from bedrock_server_manager.diagnostics.health import evaluate_health
    from bedrock_server_manager.diagnostics.models import (
        BackupsDiagnostics,
        DiagnosticOptions,
    )

    options = DiagnosticOptions()

    # Fresh install: server exists, 0 archives, no failures -> ok
    fresh = BackupsDiagnostics(
        servers=1,
        archives=0,
        total_bytes=0,
        failed=0,
        missing_keys=0,
        destination_failures=0,
        without_backup=1,
    )
    status, issues = evaluate_health(fresh, options)
    assert status == "ok"
    assert issues == []

    # Failure present -> degraded
    failed = BackupsDiagnostics(
        servers=1,
        archives=1,
        total_bytes=1000,
        failed=1,
        missing_keys=0,
        destination_failures=0,
        without_backup=0,
    )
    status, issues = evaluate_health(failed, options)
    assert status == "degraded"
    assert any(i.code == "backup_attention" for i in issues)

    # Some servers have backups, some don't -> degraded (backup_missing)
    missing = BackupsDiagnostics(
        servers=2,
        archives=5,
        total_bytes=5000,
        failed=0,
        missing_keys=0,
        destination_failures=0,
        without_backup=1,
    )
    status, issues = evaluate_health(missing, options)
    assert status == "degraded"
    assert any(i.code == "backup_missing" for i in issues)


@pytest.mark.asyncio
async def test_diagnostic_notifier_broadcasts_only_when_subscribed(app_context):
    manager = app_context.connection_manager
    service = app_context.diagnostics

    broadcasts = []

    async def mock_broadcast(topic, message):
        broadcasts.append((topic, message))
        return None

    manager.broadcast_to_topic = mock_broadcast

    # 1. No subscribers: notifier runs without broadcasting
    snapshot = await service.snapshot()
    assert service.notifier is not None
    await service.notifier(snapshot, "health_sample")
    assert broadcasts == []

    # 2. Add subscription for diagnostics
    manager.subscriptions["diagnostics"] = ["test_client"]
    await service.notifier(snapshot, "health_sample")
    assert len(broadcasts) == 1
    assert broadcasts[0][0] == "diagnostics"
    assert broadcasts[0][1]["type"] == "diagnostic_update"

    # 3. Add subscription for health
    broadcasts.clear()
    manager.subscriptions["health"] = ["test_client_2"]
    await service.notifier(snapshot, "health_transition")
    topics = [t for t, _ in broadcasts]
    assert "diagnostics" in topics
    assert "health" in topics
    health_msg = next(m for t, m in broadcasts if t == "health")
    assert health_msg["type"] == "health_update"
