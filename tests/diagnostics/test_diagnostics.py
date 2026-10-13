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
    assert result.records[0].error_type == "RuntimeError"
    await restarted.close()


@pytest.mark.asyncio
async def test_slow_and_broken_plugin_providers_do_not_hide_other_sections(db):
    options = DiagnosticOptions(provider_timeout_seconds=0.01)
    service = Diagnostics(DiagnosticHistoryStore(db, options), options)
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
