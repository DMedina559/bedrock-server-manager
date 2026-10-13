"""Authenticated readiness checks against real context dependencies."""

from bedrock_server_manager.api.models.health import GetApplicationHealthResponse


async def test_health_requires_login_and_checks_database_and_state(
    auth_client, unauth_client
):
    assert (await unauth_client.get("/api/health")).status_code == 401
    response = await auth_client.get("/api/health")
    assert response.status_code == 200
    health = GetApplicationHealthResponse.model_validate(response.json())
    assert health.checks["database"].healthy
    assert health.checks["state"].healthy
    assert set(health.checks) == {"lifecycle", "database", "state", "metrics"}


async def test_stopped_sampler_is_degraded_then_recovers(auth_client, app_context):
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
