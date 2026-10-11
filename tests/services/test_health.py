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
