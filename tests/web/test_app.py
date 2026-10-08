import asyncio

import pytest
from fastapi import Request
from pydantic import BaseModel

from bedrock_server_manager.web.app import create_web_app


def test_create_web_app_initialization(app_context):
    app = create_web_app(app_context)
    assert app.title == "Bedrock Server Manager"
    assert app.state.app_context is app_context
    assert app.openapi_url == "/api/openapi.json"


@pytest.mark.parametrize(
    "path,expected",
    [("/", 307), ("/docs", 200), ("/api/users", 404), ("/app/assets/missing.js", 404)],
)
async def test_setup_middleware_with_actual_empty_database(
    unauth_client, path, expected
):
    response = await unauth_client.get(path, follow_redirects=False)
    assert response.status_code == expected
    if expected == 307:
        assert response.headers["location"].endswith("/app")


async def test_authenticated_request_populates_user_state(
    test_app, auth_client, test_user
):
    @test_app.get("/test-middleware-user")
    async def get_user(request: Request):
        return {"username": request.state.current_user.username}

    response = await auth_client.get("/test-middleware-user")
    assert response.json()["username"] == test_user.username


async def test_lifespan_owns_monitors_on_the_application_loop(app_context):
    app = create_web_app(app_context)
    async with app.router.lifespan_context(app):
        assert app_context.loop is asyncio.get_running_loop()
        resource_task = app_context.resource_monitor._task
        process_task = app_context.bedrock_process_manager.monitoring_task
        assert resource_task is not None and not resource_task.done()
        assert process_task is not None and not process_task.done()
        assert app_context.log_streamer._task is not None
    assert resource_task.done()
    assert process_task.done()


async def test_validation_errors_have_safe_envelopes(test_app, auth_client):
    class Output(BaseModel):
        value: int

    @test_app.get("/api/test-input")
    async def input_route(value: int):
        return {"value": value}

    @test_app.get("/api/test-output", response_model=Output)
    async def output_route():
        return {"value": "private-invalid-value"}

    response = await auth_client.get("/api/test-input?value=invalid")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    response = await auth_client.get("/api/test-output")
    assert response.status_code == 500
    assert "private-invalid-value" not in response.text


async def test_failed_plugin_load_is_isolated_from_application_startup(
    app_context, tmp_path
):
    plugin = tmp_path / "plugins" / "broken.py"
    plugin.write_text("""from bedrock_server_manager import PluginBase
class Broken(PluginBase):
    version = "1.0"
    async def on_load(self):
        raise RuntimeError("startup failed")
""")
    manager = app_context.plugin_manager
    await app_context.plugin_service.register_or_update_plugin("broken", enabled=True)
    app = create_web_app(app_context)
    async with app.router.lifespan_context(app):
        assert manager.get_plugin_status("broken") == "ERROR"
        assert not manager.plugins
    assert app_context.bedrock_process_manager.monitoring_task.done()


async def test_partial_startup_failure_drains_started_components(
    app_context, monkeypatch
):
    def fail_resource_start():
        raise RuntimeError("resource monitor startup failed")

    monkeypatch.setattr(app_context.resource_monitor, "start", fail_resource_start)
    app = create_web_app(app_context)
    with pytest.raises(RuntimeError, match="resource monitor startup failed"):
        async with app.router.lifespan_context(app):
            pytest.fail("Startup must propagate the failure")
    task = app_context.bedrock_process_manager.monitoring_task
    assert task is not None and task.done()
    assert not app_context.task_manager.futures
    assert not app_context.connection_manager.active_connections
