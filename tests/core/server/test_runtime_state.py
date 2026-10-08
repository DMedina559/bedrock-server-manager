"""Runtime snapshots follow verified processes rather than independent caches."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from bedrock_server_manager.state.models import ServerRuntimeInfo


async def test_process_probe_updates_runtime_and_stopped_probe_clears_stats(
    real_bedrock_server, monkeypatch
):
    server = real_bedrock_server
    server._process = SimpleNamespace(pid=123, poll=lambda: None)
    assert await server.is_running()
    snapshot = server.state.runtime.get_server_runtime(server.server_name)
    assert snapshot.running and snapshot.pid == 123
    server._runtime_state.update_server_runtime(
        server.server_name, cpu_percent=20.0, memory_mb=100.0
    )
    server._process = None
    monkeypatch.setattr(
        "bedrock_server_manager.core.server.process_mixin.system_base.is_server_running",
        AsyncMock(return_value=False),
    )
    assert not await server.is_running()
    snapshot = server.state.runtime.get_server_runtime(server.server_name)
    assert (
        snapshot.pid is None and snapshot.cpu_percent == 0 and snapshot.memory_mb == 0
    )


@pytest.mark.parametrize("values", [{"pid": 1}, {"players_online": 1}])
def test_runtime_rejects_inconsistent_snapshots(values):
    with pytest.raises(ValidationError):
        ServerRuntimeInfo.model_validate(values)


async def test_running_probe_replaces_stale_process_identity(
    real_bedrock_server, monkeypatch
):
    server = real_bedrock_server
    server._process = SimpleNamespace(pid=111, returncode=0)
    recovered = SimpleNamespace(pid=222)
    monkeypatch.setattr(
        "bedrock_server_manager.core.server.process_mixin.system_base.is_server_running",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        "bedrock_server_manager.core.server.process_mixin.system_process.get_verified_bedrock_process",
        AsyncMock(return_value=recovered),
    )
    assert await server.is_running()
    assert server._process is recovered
    assert server.state.runtime.get_server_runtime(server.server_name).pid == 222


@pytest.mark.parametrize(
    "failure", [OSError("pid write failed"), __import__("asyncio").CancelledError()]
)
async def test_failed_start_reaps_child_and_closes_handles(
    real_bedrock_server, monkeypatch, failure
):
    from unittest.mock import Mock

    from bedrock_server_manager.error import ServerStartError

    server = real_bedrock_server
    child = SimpleNamespace(
        pid=123, terminate=Mock(), kill=Mock(), wait=AsyncMock(return_value=0)
    )
    monkeypatch.setattr(server, "is_installed", AsyncMock(return_value=True))
    monkeypatch.setattr(server, "is_running", AsyncMock(return_value=False))
    monkeypatch.setattr(server, "set_status_in_config", AsyncMock())
    monkeypatch.setattr("asyncio.create_subprocess_exec", AsyncMock(return_value=child))
    monkeypatch.setattr(
        "bedrock_server_manager.core.server.process_mixin.system_process.write_pid_to_file",
        AsyncMock(side_effect=failure),
    )
    with pytest.raises((ServerStartError, __import__("asyncio").CancelledError)):
        await server.start()
    child.terminate.assert_called_once()
    child.wait.assert_awaited_once()
    assert server._process is None
    assert server._log_file_handle is None
    assert not server.state.runtime.get_server_runtime(server.server_name).running


async def test_cancel_during_spawn_retains_child_until_cleanup(
    real_bedrock_server, monkeypatch
):
    import asyncio
    from unittest.mock import Mock

    server = real_bedrock_server
    started, released = asyncio.Event(), asyncio.Event()
    child = SimpleNamespace(
        pid=123, terminate=Mock(), kill=Mock(), wait=AsyncMock(return_value=0)
    )

    async def spawn(*args, **kwargs):
        started.set()
        await released.wait()
        return child

    monkeypatch.setattr(server, "is_installed", AsyncMock(return_value=True))
    monkeypatch.setattr(server, "is_running", AsyncMock(return_value=False))
    monkeypatch.setattr(server, "set_status_in_config", AsyncMock())
    monkeypatch.setattr("asyncio.create_subprocess_exec", spawn)
    start = asyncio.create_task(server.start())
    await started.wait()
    start.cancel()
    released.set()
    with pytest.raises(asyncio.CancelledError):
        await start
    child.terminate.assert_called_once()
    assert server._process is None
    assert server._log_file_handle is None
