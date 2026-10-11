"""Core metrics lifecycle and transport contracts."""

import asyncio
import json
import os
from contextlib import nullcontext
from types import SimpleNamespace

import psutil

from bedrock_server_manager.api.models.metrics import GetApplicationMetricsResponse
from bedrock_server_manager.services.metrics_service import MetricsService


async def test_metrics_endpoint_requires_login_and_returns_shared_snapshot(
    auth_client, unauth_client, app_context
):
    assert (await unauth_client.get("/api/metrics")).status_code == 401
    response = await auth_client.get("/api/metrics")
    assert response.status_code == 200
    data = GetApplicationMetricsResponse.model_validate(response.json())
    assert data.latest.app_ram_mb is None or data.latest.app_ram_mb > 0
    assert data.latest.asyncio_task_count > 0
    assert data.latest.epoch and data.latest.revision
    service = app_context.metrics_service
    count = len(service._history)
    first = await service.snapshot()
    first.latest.servers.clear()
    second = await service.snapshot()
    assert len(service._history) == count
    assert second.latest.app_ram_mb == data.latest.app_ram_mb


async def test_metrics_publish_typed_frames_and_stop_with_context(
    app_context, subscribed_socket
):
    service = app_context.metrics_service
    service.start()
    task = service._task
    service.start()
    assert service._task is task
    async with subscribed_socket("application-metrics") as socket:
        async with asyncio.timeout(8):
            while True:
                message = json.loads(await socket.recv())
                if message.get("type") == "resource_update":
                    break
        assert message["topic"] == "application-metrics"
        assert message["data"]["epoch"]
        assert message["data"]["revision"] > 0
        assert message["data"]["timestamp"] > 0
    await service.shutdown()
    assert task.done()
    assert service._task is None


async def test_history_is_bounded_and_stopped_server_values_are_unavailable(
    app_context, real_bedrock_server, monkeypatch
):
    service = MetricsService(app_context)
    monkeypatch.setattr(service, "_collect", lambda: {"app_ram_mb": 12.0})
    for _ in range(service.history_limit + 1):
        await service.sample()
    response = await service.snapshot()
    assert len(response.history) == service.history_limit
    assert response.latest == response.history[-1]
    server = next(
        item
        for item in response.latest.servers
        if item.server_name == real_bedrock_server.server_name
    )
    assert server.pid is None and server.cpu_percent is None
    assert all(
        a.revision < b.revision for a, b in zip(response.history, response.history[1:])
    )


def test_sampler_uses_persistent_cpu_baselines_and_does_not_report_counter_resets_as_rates(
    app_context, monkeypatch
):
    service = MetricsService(app_context)
    process = SimpleNamespace(
        cpu_percent=lambda interval: 12.0,
        oneshot=nullcontext,
        memory_info=lambda: SimpleNamespace(rss=1024**2),
        num_threads=lambda: 2,
        create_time=lambda: 1.0,
    )
    monkeypatch.setattr(psutil, "Process", lambda pid: process)
    first = service._collect()
    assert "app_cpu_percent" not in first
    assert "net_tx_kib_s" not in first
    process = service._process
    second = service._collect()
    assert service._process is process
    assert second["app_cpu_percent"] >= 0
    service._net = SimpleNamespace(bytes_sent=10000, bytes_recv=10000)
    monkeypatch.setattr(
        psutil, "net_io_counters", lambda: SimpleNamespace(bytes_sent=1, bytes_recv=1)
    )
    reset = service._collect()
    assert "net_tx_kib_s" not in reset
    assert "net_rx_kib_s" not in reset


def test_os_access_errors_remain_unavailable_without_breaking_other_measurements(
    app_context, monkeypatch
):
    service = MetricsService(app_context)

    def denied(*args):
        raise psutil.AccessDenied(os.getpid())

    monkeypatch.setattr(psutil, "Process", denied)
    values = service._collect()
    assert "app_ram_mb" not in values
    assert values["sys_ram_total_mb"] > 0


async def test_concurrent_initial_reads_share_one_sample(app_context, monkeypatch):
    service = MetricsService(app_context)
    monkeypatch.setattr(service, "_collect", lambda: {})
    snapshots = await asyncio.gather(*(service.snapshot() for _ in range(5)))
    assert len(service._history) == 1
    assert len({snapshot.latest.revision for snapshot in snapshots}) == 1


async def test_server_metrics_preserve_cpu_above_one_core_and_ignore_uptime(
    app_context, real_bedrock_server, monkeypatch
):
    async def process_info():
        return {"pid": 123, "cpu_percent": 250.0, "memory_mb": 64.0, "uptime": "1h"}

    monkeypatch.setattr(real_bedrock_server, "get_process_info", process_info)
    service = MetricsService(app_context)
    monkeypatch.setattr(service, "_collect", lambda: {})
    snapshot = await service.snapshot()
    server = next(
        item
        for item in snapshot.latest.servers
        if item.server_name == real_bedrock_server.server_name
    )
    assert server.pid == 123
    assert server.cpu_percent == 250.0
    assert server.memory_mb == 64.0


async def test_metrics_count_managed_plugin_operations_until_completion(app_context):
    release = asyncio.Event()
    manager = app_context.task_manager
    task_id = await manager.run_task(release.wait, _plugin_owner="test_plugin")
    try:
        sample = await app_context.metrics_service.sample()
        assert sample.background_task_count == 1
        release.set()
        await manager.futures[task_id]
        sample = await app_context.metrics_service.sample()
        assert sample.background_task_count == 0
    finally:
        release.set()
