"""Real component lifecycles, rollback, and bounded cancellation."""

import asyncio
from contextlib import asynccontextmanager

import pytest
from fastapi import APIRouter, FastAPI

from bedrock_server_manager.context import AppContext
from bedrock_server_manager.plugins.lifespan import RouterLifespan
from bedrock_server_manager.services.lifecycle import LifecyclePhase, run_stage
from bedrock_server_manager.utils.general import startup_checks
from bedrock_server_manager.web.app import create_web_app


async def test_startup_shutdown_are_idempotent_and_reload_restarts(
    app_context, monkeypatch
):
    app = create_web_app(app_context)
    async with app.router.lifespan_context(app):
        assert app_context.lifecycle_phase == LifecyclePhase.READY
        monitor = app_context.metrics_service._task
        await app_context.startup()
        assert app_context.metrics_service._task is monitor
    assert app_context.lifecycle_phase == LifecyclePhase.STOPPED
    cleanup = app_context._shutdown_task
    await app_context.shutdown()
    assert app_context._shutdown_task is cleanup
    with pytest.raises(RuntimeError, match="Reload"):
        await app_context.startup()
    await app_context.load()
    app = create_web_app(app_context)
    async with app.router.lifespan_context(app):
        assert app_context.lifecycle_phase == LifecyclePhase.READY
        assert app_context.metrics_service._task is not monitor
        assert not app_context.bedrock_process_manager._shutdown_event.is_set()


async def test_partial_startup_keeps_original_failure_and_stops_started_components(
    app_context, monkeypatch
):
    def fail():
        raise ValueError("resource startup failure")

    monkeypatch.setattr(app_context.resource_monitor, "start", fail)
    app = create_web_app(app_context)
    with pytest.raises(ValueError, match="resource startup failure"):
        async with app.router.lifespan_context(app):
            pytest.fail("Must not become ready")
    assert app_context.lifecycle_phase == LifecyclePhase.FAILED
    assert app_context.bedrock_process_manager.monitoring_task.done()
    assert app_context._metrics_service is None
    assert app_context.db.engine is None


async def test_stuck_operation_deadline_does_not_skip_storage_cleanup(tmp_path):
    context = AppContext(
        config_dir=str(tmp_path / "config"),
        data_dir=str(tmp_path),
        db_url=f"sqlite:///{tmp_path / 'lifecycle.db'}",
    )
    await context.load()
    await context.settings.set("lifecycle.task_drain_timeout_seconds", 0.02)
    entered = asyncio.Event()
    cancelled = asyncio.Event()

    async def operation():
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    await context.task_manager.run_task(operation)
    await entered.wait()
    with pytest.raises(ExceptionGroup, match="Application shutdown failed"):
        await context.shutdown()
    assert cancelled.is_set()
    assert context.db.engine is None
    assert context.lifecycle_phase == LifecyclePhase.FAILED


async def test_uncooperative_stage_has_bounded_cancellation_grace():
    release = asyncio.Event()
    finished = asyncio.Event()

    async def operation():
        try:
            await release.wait()
        except asyncio.CancelledError:
            await release.wait()
        finally:
            finished.set()

    try:
        async with asyncio.timeout(1):
            with pytest.raises(TimeoutError, match="stuck plugin"):
                await run_stage("stuck plugin", operation, 0.02, 0.02)
    finally:
        release.set()
        await finished.wait()


async def test_router_shutdown_deadline_preserves_owner_task_and_closes():
    exited = asyncio.Event()

    @asynccontextmanager
    async def lifespan(app):
        owner = asyncio.current_task()
        try:
            yield
            await asyncio.Event().wait()
        finally:
            assert asyncio.current_task() is owner
            exited.set()

    router = RouterLifespan(
        FastAPI(), [APIRouter(lifespan=lifespan)], timeout=0.02, grace=0.02
    )
    await router.start()
    with pytest.raises(TimeoutError, match="router lifespan"):
        await router.close()
    assert router.task.done()
    assert exited.is_set()


async def test_shutdown_closes_real_websocket(subscribed_socket, app_context):
    async with subscribed_socket("application-metrics") as socket:
        await app_context.shutdown()
        await asyncio.wait_for(socket.wait_closed(), 2)
        assert socket.close_code == 1001
        assert not app_context.connection_manager.active_connections
        assert not app_context.connection_manager.subscriptions


async def test_server_stop_hooks_run_before_plugins_are_unloaded(
    app_context, real_bedrock_server
):
    manager = app_context.plugin_manager
    path = manager.plugin_dirs[0] / "shutdown_order.py"
    path.write_text("""
from bedrock_server_manager.plugins.plugin_base import PluginBase
from bedrock_server_manager.plugins import app_event
class ShutdownOrder(PluginBase):
    version = "1.0.0"
    author = "Tests"
    description = "Records shutdown events"
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.events = []
    @app_event("after_server_stop")
    async def stopped(self, **kwargs):
        self.events.append("server stopped")
    async def on_unload(self):
        self.events.append("unloaded")
""")
    await manager.enable_plugin("shutdown_order", load_immediately=True)
    plugin = manager.plugins[0]
    await real_bedrock_server.start()
    await app_context.shutdown()
    assert plugin.events == ["server stopped", "unloaded"]


async def test_hanging_plugin_hook_is_bounded_and_other_cleanup_runs(tmp_path):
    context = AppContext(
        config_dir=str(tmp_path / "config"),
        data_dir=str(tmp_path),
        db_url=f"sqlite:///{tmp_path / 'hooks.db'}",
    )
    await context.load()
    directory = tmp_path / "plugins"
    directory.mkdir(exist_ok=True)
    context.plugin_manager.plugin_dirs = [directory]
    (directory / "hanging.py").write_text("""
import asyncio
from bedrock_server_manager.plugins.plugin_base import PluginBase
class Hanging(PluginBase):
    version = "1.0.0"
    author = "Tests"
    description = "Stuck hook"
    async def on_unload(self):
        await asyncio.Event().wait()
""")
    await context.settings.set("lifecycle.plugin_timeout_seconds", 0.02)
    await context.plugin_manager.enable_plugin("hanging", load_immediately=True)
    async with asyncio.timeout(2):
        with pytest.raises(ExceptionGroup, match="Application shutdown failed"):
            await context.shutdown()
    assert not context.plugin_manager.plugins
    assert context.db.engine is None
    assert context.lifecycle_phase == LifecyclePhase.FAILED


async def test_shutdown_during_startup_cancels_start_and_never_becomes_ready(
    app_context, monkeypatch
):
    entered = asyncio.Event()

    async def blocked():
        entered.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(app_context.resource_monitor, "start", blocked)
    caller = asyncio.create_task(app_context.startup())
    await entered.wait()
    await app_context.shutdown()
    with pytest.raises(asyncio.CancelledError):
        await caller
    assert app_context.lifecycle_phase == LifecyclePhase.FAILED
    assert app_context.db.engine is None
    assert app_context.bedrock_process_manager.monitoring_task.done()


async def test_startup_error_survives_rollback_failure(tmp_path, monkeypatch):
    context = AppContext(
        config_dir=str(tmp_path / "config"),
        data_dir=str(tmp_path),
        db_url=f"sqlite:///{tmp_path / 'rollback.db'}",
    )
    await context.load()
    startup_checks(context)

    def fail_start():
        raise ValueError("original startup error")

    async def fail_flush():
        raise RuntimeError("flush failed during rollback")

    monkeypatch.setattr(context.resource_monitor, "start", fail_start)
    monkeypatch.setattr(context, "flush", fail_flush)
    with pytest.raises(ValueError, match="original startup error") as error:
        await context.startup()
    assert any("rollback also failed" in note for note in error.value.__notes__)
    assert context.db.engine is None
    assert context.lifecycle_phase == LifecyclePhase.FAILED
