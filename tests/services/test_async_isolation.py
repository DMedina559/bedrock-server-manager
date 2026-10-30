"""A slow server must not stop observations or maintenance for its peers."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from bedrock_server_manager.scheduler.service import Scheduler
from bedrock_server_manager.services.lifecycle import LifecyclePhase
from bedrock_server_manager.utils.general import ReentrantAsyncLock


async def test_monitor_keeps_peer_responsive_and_drains_checks(
    app_context, monkeypatch
):
    await app_context.settings.set("monitoring.process_interval_sec", 1)
    manager = app_context.bedrock_process_manager
    manager.servers = {name: object() for name in ("slow", "healthy")}
    entered, observed = asyncio.Event(), asyncio.Event()
    calls = []

    async def observe(name, server, *, scan_players):
        calls.append(name)
        if name == "slow":
            entered.set()
            await asyncio.Event().wait()
        else:
            observed.set()

    monkeypatch.setattr(manager, "_observe_server", observe)
    await manager.start()
    try:
        await asyncio.wait_for(entered.wait(), 3)
        await asyncio.wait_for(observed.wait(), 1)
        assert calls.count("slow") == 1
        assert manager._server_checks["slow"].done() is False
    finally:
        await manager.quiesce()
        manager.servers.clear()
    assert not manager._server_checks


async def test_slow_maintenance_does_not_delay_other_servers(monkeypatch):
    entered, observed = asyncio.Event(), asyncio.Event()

    async def slow():
        entered.set()
        await asyncio.Event().wait()

    async def healthy():
        observed.set()

    servers = {
        name: SimpleNamespace(
            operation_lock=ReentrantAsyncLock(),
            backups=SimpleNamespace(maintain_backups=work),
        )
        for name, work in (("slow", slow), ("healthy", healthy))
    }
    context = SimpleNamespace(
        db=None,
        settings={},
        lifecycle_phase=LifecyclePhase.READY,
        state=SimpleNamespace(servers=SimpleNamespace(servers=servers)),
        get_server=lambda name, **kwargs: servers[name],
    )
    from bedrock_server_manager.db.repositories.scheduler import SchedulerRepository

    monkeypatch.setattr(SchedulerRepository, "recover", AsyncMock())
    context.storage = SimpleNamespace(scheduler_repo=SchedulerRepository(None))
    context.state.runtime = SimpleNamespace(scheduler={})
    maintenance = Scheduler(context)
    monkeypatch.setattr(maintenance, "configurations", AsyncMock(return_value={}))
    maintenance.start()
    try:
        await asyncio.wait_for(entered.wait(), 2)
        await asyncio.wait_for(observed.wait(), 1)
        assert not maintenance._jobs["slow"].done()
    finally:
        await maintenance.shutdown()
    assert not maintenance._jobs


async def test_loop_lag_is_visible_in_diagnostics(app_context):
    service = app_context.metrics_service
    await service.sample(lag_ms=150)
    await service.sample(lag_ms=2)
    snapshot = service.diagnostic_snapshot()
    assert snapshot.event_loop_lag_ms == 2
    assert snapshot.recent_max_event_loop_lag_ms == 150
    assert snapshot.event_loop_lag_breaches == 1
