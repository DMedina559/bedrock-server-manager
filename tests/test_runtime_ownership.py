import asyncio
import threading
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import APIRouter, FastAPI

from bedrock_server_manager.api.backup_restore import backup_config_file
from bedrock_server_manager.api.models.backup_restore import BackupConfigFileRequest
from bedrock_server_manager.plugins.plugin_base import PluginBase
from bedrock_server_manager.web.tasks import TaskManager


@pytest.mark.asyncio
async def test_overlapping_starts_retain_one_child(real_bedrock_server, monkeypatch):
    server = real_bedrock_server
    both = asyncio.Event()
    release = asyncio.Event()
    children = []
    handles = []

    async def spawn(*args, **kwargs):
        child = SimpleNamespace(
            pid=100 + len(children),
            returncode=None,
            terminate=Mock(),
            wait=AsyncMock(return_value=0),
        )
        children.append(child)
        handles.append(kwargs["stdout"])
        both.set()
        await release.wait()
        return child

    monkeypatch.setattr(server, "is_installed", AsyncMock(return_value=True))
    monkeypatch.setattr(
        server, "is_running", AsyncMock(side_effect=lambda: server._process is not None)
    )
    monkeypatch.setattr(server, "set_status_in_config", AsyncMock())
    monkeypatch.setattr("asyncio.create_subprocess_exec", spawn)
    monkeypatch.setattr(
        "bedrock_server_manager.core.server.process_mixin.system_process.write_pid_to_file",
        AsyncMock(),
    )
    starts = [asyncio.create_task(server.start()) for _ in range(2)]
    try:
        await asyncio.wait_for(both.wait(), 2)
        release.set()
        results = await asyncio.gather(*starts, return_exceptions=True)
        from bedrock_server_manager.error import ServerStartError

        assert len(children) == 1
        assert sum(isinstance(result, ServerStartError) for result in results) == 1
    finally:
        release.set()
        await asyncio.gather(*starts, return_exceptions=True)
        for handle in handles:
            handle.close()
        server._process = None
        server._log_file_handle = None


@pytest.mark.asyncio
async def test_load_unload_overlap(app_context, monkeypatch):
    pm = app_context.plugin_manager
    entered = asyncio.Event()
    release = asyncio.Event()

    class Slow(PluginBase):
        async def on_load(self):
            entered.set()
            await release.wait()

        def get_fastapi_routers(self):
            router = APIRouter()

            @router.get("/audit-race")
            async def route():
                return {}

            return [router]

    pm.plugin_config = {"slow": {"enabled": True}}
    monkeypatch.setattr(
        pm, "_find_plugin_path", lambda _: __import__("pathlib").Path("slow.py")
    )
    monkeypatch.setattr(pm, "_get_plugin_class_from_path", lambda *args: Slow)
    app = FastAPI()
    pm.bind_web_app(app)
    task = asyncio.create_task(pm.load_plugin_by_name("slow"))
    await entered.wait()
    unload = asyncio.create_task(pm.unload_plugin_by_name("slow"))
    await asyncio.sleep(0)
    assert not unload.done()
    release.set()
    assert await task
    assert await unload
    assert not pm.plugins and "/audit-race" not in app.openapi()["paths"]
    assert pm.get_plugin_status("slow") == "UNLOADED"


@pytest.mark.asyncio
async def test_async_backup_cancellation_retains_lock_until_thread_finishes(
    app_context, real_bedrock_server, monkeypatch
):
    server = real_bedrock_server
    started = threading.Event()
    release = threading.Event()
    finished = threading.Event()

    def copy(*args):
        started.set()
        release.wait(3)
        finished.set()

    monkeypatch.setattr(
        "bedrock_server_manager.core.server.backup_restore_mixin.shutil.copy2", copy
    )
    monkeypatch.setattr(
        "bedrock_server_manager.core.server.backup_restore_mixin.shutil.copystat",
        lambda *args: None,
    )
    server_dir = __import__("pathlib").Path(server.server_dir)
    (server_dir / "server.properties").write_text("test")
    tm = TaskManager(None)
    task_id = await tm.run_task(
        backup_config_file,
        request=BackupConfigFileRequest(
            server_name=server.server_name, file_to_backup="server.properties"
        ),
        app_context=app_context,
    )
    try:
        assert await asyncio.to_thread(started.wait, 2)
        await tm.cancel_task(task_id)
        await asyncio.sleep(0.05)
        assert (await tm.get_task(task_id)).status == "cancelling"
        assert not finished.is_set() and server.operation_lock.locked()
    finally:
        release.set()
        await asyncio.to_thread(finished.wait, 2)
        await tm.shutdown()


@pytest.mark.asyncio
async def test_hot_router_lifespan_enters_and_exits(app_context):
    pm = app_context.plugin_manager
    app = FastAPI()
    pm.bind_web_app(app)
    counts = []

    @asynccontextmanager
    async def lifespan(app):
        counts.append("enter")
        try:
            yield
        finally:
            counts.append("exit")

    router = APIRouter(lifespan=lifespan)
    async with app.router.lifespan_context(app):
        await pm._register_routers("hot", [router])
        assert counts == ["enter"]
        await pm._close_router_lifespan("hot")
        assert counts == ["enter", "exit"]
    assert counts == ["enter", "exit"]


@pytest.mark.asyncio
async def test_shutdown_drains_tasks_before_final_server_stop(app_context, monkeypatch):
    from unittest.mock import MagicMock

    from bedrock_server_manager.core.bedrock_process_manager import (
        BedrockProcessManager,
    )
    from bedrock_server_manager.plugins.runtime_capabilities import (
        server_lifecycle_manager,
    )

    entered = asyncio.Event()
    release = asyncio.Event()
    running = True

    async def probe():
        return running

    async def stop(*args, **kwargs):
        nonlocal running
        running = False

    async def start(*args, **kwargs):
        nonlocal running
        running = True

    monkeypatch.setattr("bedrock_server_manager.api.server.stop_server", stop)
    monkeypatch.setattr("bedrock_server_manager.api.server.start_server", start)
    server = SimpleNamespace(server_name="test", is_running=probe, stop=stop)
    monkeypatch.setattr(app_context, "get_server", lambda _: server)
    api = MagicMock()
    api.server.stop = AsyncMock(side_effect=stop)
    manager = BedrockProcessManager(app_context.settings, app_context.storage, api=api)
    manager.servers["test"] = server
    tm = TaskManager(None)

    async def restore():
        async with server_lifecycle_manager(
            "test", stop_before=True, app_context=app_context
        ):
            entered.set()
            await release.wait()

    await tm.run_task(restore)
    await entered.wait()
    app_context._bedrock_process_manager = manager
    app_context._task_manager = tm
    app_context._plugin_manager = None
    shutdown = asyncio.create_task(app_context.shutdown())
    await asyncio.sleep(0.05)
    assert manager._shutdown_event.is_set() and not shutdown.done()
    release.set()
    await shutdown
    assert not running and app_context._db.engine is None


@pytest.mark.asyncio
async def test_router_lifespans_follow_live_load_unload_reload(
    app_context, monkeypatch
):
    pm = app_context.plugin_manager
    counts = []

    @asynccontextmanager
    async def lifespan(app):
        counts.append("enter")
        try:
            yield
        finally:
            counts.append("exit")

    class WebPlugin(PluginBase):
        def get_fastapi_routers(self):
            router = APIRouter(lifespan=lifespan)
            router.add_api_route("/resource", lambda: {})
            return [router]

    pm.plugin_config = {"web": {"enabled": True}}
    monkeypatch.setattr(
        pm, "_find_plugin_path", lambda _: __import__("pathlib").Path("web.py")
    )
    monkeypatch.setattr(pm, "_get_plugin_class_from_path", lambda *args: WebPlugin)
    app = FastAPI()
    pm.bind_web_app(app)
    await pm.load_plugin_by_name("web")
    assert counts == []
    async with app.router.lifespan_context(app):
        assert counts == ["enter"]
        await pm.unload_plugin_by_name("web")
        assert counts == ["enter", "exit"]
        await pm.load_plugin_by_name("web")
        assert counts == ["enter", "exit", "enter"]
    assert counts == ["enter", "exit", "enter", "exit"]
    await pm.unload_plugins()
    assert counts == ["enter", "exit", "enter", "exit"]


@pytest.mark.asyncio
async def test_failed_hot_lifespan_rolls_back_routes_and_resources(
    app_context, monkeypatch
):
    pm = app_context.plugin_manager
    closed = []

    @asynccontextmanager
    async def successful(app):
        try:
            yield
        finally:
            closed.append(True)

    @asynccontextmanager
    async def broken(app):
        raise RuntimeError("startup failed")
        yield

    class BrokenPlugin(PluginBase):
        def get_fastapi_routers(self):
            return [APIRouter(lifespan=successful), APIRouter(lifespan=broken)]

    pm.plugin_config = {"broken": {"enabled": True}}
    monkeypatch.setattr(
        pm, "_find_plugin_path", lambda _: __import__("pathlib").Path("broken.py")
    )
    monkeypatch.setattr(pm, "_get_plugin_class_from_path", lambda *args: BrokenPlugin)
    app = FastAPI()
    pm.bind_web_app(app)
    async with app.router.lifespan_context(app):
        assert not await pm.load_plugin_by_name("broken")
        assert closed == [True]
        assert pm.get_plugin_status("broken") == "ERROR"
        assert not pm.plugins and not pm._router_lifespans
        assert not pm.plugin_fastapi_routers


@pytest.mark.asyncio
async def test_router_event_handlers_do_not_duplicate_on_route_rebuild(app_context):
    pm = app_context.plugin_manager
    app = FastAPI()
    pm.bind_web_app(app)
    started, stopped = Mock(), Mock()
    router = APIRouter(on_startup=[started], on_shutdown=[stopped])
    await pm._register_routers("events", [router])
    pm._sync_web_routes("events")
    pm._sync_web_routes("events")
    async with app.router.lifespan_context(app):
        started.assert_called_once()
    stopped.assert_called_once()
