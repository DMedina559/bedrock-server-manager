"""Authenticated readiness checks against real context dependencies."""

import asyncio

import pytest_asyncio

from bedrock_server_manager.api.models.health import GetApplicationHealthResponse


async def wait_for_scheduler(service):
    async with asyncio.timeout(5):
        while not service.check_health():
            if service.task is not None and service.task.done():
                await service.task
            await asyncio.sleep(0.01)


@pytest_asyncio.fixture
async def running_health_services(app_context):
    """Start the actual background dependencies checked by aggregate health."""
    metrics = app_context.metrics_service
    scheduler = app_context.scheduler
    metrics.start()
    await metrics.snapshot()
    scheduler.start()
    try:
        await wait_for_scheduler(scheduler)
        yield
    finally:
        await scheduler.shutdown()
        await metrics.shutdown()


async def test_health_requires_login_and_checks_database_and_state(
    auth_client, unauth_client, running_health_services
):
    assert (await unauth_client.get("/api/health")).status_code == 401
    response = await auth_client.get("/api/health")
    assert response.status_code == 200
    health = GetApplicationHealthResponse.model_validate(response.json())
    assert health.checks["database"].healthy
    assert health.checks["state"].healthy
    assert set(health.checks) == {
        "lifecycle",
        "database",
        "state",
        "metrics",
        "scheduler",
        "timezone_data",
    }
    assert all(check.healthy for check in health.checks.values())


async def test_stopped_sampler_is_degraded_then_recovers(
    auth_client, app_context, running_health_services
):
    service = app_context.metrics_service
    await service.shutdown()
    response = await auth_client.get("/api/health")
    assert response.json()["health"] == "degraded"
    assert not response.json()["checks"]["metrics"]["healthy"]
    service.start()
    await service.snapshot()
    response = await auth_client.get("/api/health")
    assert response.json()["health"] == "healthy"


async def test_database_failure_is_sanitized(auth_client, app_context, monkeypatch):
    async def fail():
        raise RuntimeError("secret database connection string")

    monkeypatch.setattr(app_context.db, "check_health", fail)
    response = await auth_client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["health"] == "degraded"
    assert not response.json()["checks"]["database"]["healthy"]
    assert "secret" not in response.text


async def test_health_and_diagnostics_share_web_readiness(auth_client, app_context):
    from bedrock_server_manager.services.lifecycle import LifecyclePhase
    from bedrock_server_manager.web.runtime import WebRuntime

    original = app_context._web_runtime
    runtime = WebRuntime()
    runtime.attach(lambda: None)
    app_context._web_runtime = runtime
    try:
        assert app_context.lifecycle_phase == LifecyclePhase.READY
        health = (await auth_client.get("/api/health")).json()
        diagnostics = await app_context.diagnostics.snapshot("runtime")
        assert not health["ready"] and not health["checks"]["lifecycle"]["healthy"]
        assert diagnostics.summary.ready is False
        runtime.ready()
        health = (await auth_client.get("/api/health")).json()
        diagnostics = await app_context.diagnostics.snapshot("runtime")
        assert health["ready"] and diagnostics.summary.ready is True
        runtime.request_shutdown("signal")
        assert not (await auth_client.get("/api/health")).json()["ready"]
        assert (
            await app_context.diagnostics.snapshot("runtime")
        ).summary.ready is False
    finally:
        app_context._web_runtime = original


async def test_stopped_scheduler_is_degraded_then_recovers(
    auth_client, app_context, running_health_services
):
    scheduler = app_context.scheduler
    await scheduler.shutdown()
    health = (await auth_client.get("/api/health")).json()
    assert health["health"] == "degraded"
    assert not health["checks"]["scheduler"]["healthy"]
    assert health["checks"]["metrics"]["healthy"]
    scheduler.start()
    await wait_for_scheduler(scheduler)
    recovered = (await auth_client.get("/api/health")).json()
    assert recovered["checks"]["scheduler"]["healthy"]
    assert recovered["health"] == "healthy"


async def test_unavailable_timezone_data_is_degraded_then_recovers(
    auth_client, running_health_services, monkeypatch
):
    from bedrock_server_manager.utils import timezones

    monkeypatch.setattr(timezones, "timezone_database_available", lambda: False)
    health = (await auth_client.get("/api/health")).json()
    assert health["health"] == "degraded"
    assert not health["checks"]["timezone_data"]["healthy"]
    assert health["checks"]["scheduler"]["healthy"]
    monkeypatch.setattr(timezones, "timezone_database_available", lambda: True)
    recovered = (await auth_client.get("/api/health")).json()
    assert recovered["checks"]["timezone_data"]["healthy"]
    assert recovered["health"] == "healthy"
