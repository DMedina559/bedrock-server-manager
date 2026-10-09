"""Runtime snapshots follow verified processes rather than independent caches."""

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from bedrock_server_manager.state.models import ServerRuntimeInfo


async def test_process_probe_updates_runtime_and_stopped_probe_clears_stats(
    real_bedrock_server,
):
    server = real_bedrock_server
    await server.start()
    child = server.process._process
    assert await server.is_running()
    snapshot = server.state.runtime.get_server_runtime(server.server_name)
    assert snapshot.running and snapshot.pid == child.pid
    server._runtime_state.update_server_runtime(
        server.server_name, cpu_percent=20.0, memory_mb=100.0
    )
    await server.stop()
    assert child.returncode is not None
    assert not await server.is_running()
    snapshot = server.state.runtime.get_server_runtime(server.server_name)
    assert not snapshot.running
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
    server.process._process = SimpleNamespace(pid=111, returncode=0)
    recovered = SimpleNamespace(pid=222)
    monkeypatch.setattr(
        "bedrock_server_manager.core.server.process.system_base.is_server_running",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        "bedrock_server_manager.core.server.process.system_process.get_verified_bedrock_process",
        AsyncMock(return_value=recovered),
    )
    assert await server.is_running()
    assert server.process._process is recovered
    assert server.state.runtime.get_server_runtime(server.server_name).pid == 222


@pytest.mark.parametrize("failure_type", [OSError, asyncio.CancelledError])
async def test_failed_start_reaps_child_and_closes_handles(
    real_bedrock_server, monkeypatch, failure_type
):
    from bedrock_server_manager.core.system import process
    from bedrock_server_manager.error import ServerStartError

    server = real_bedrock_server
    observed = {}
    write_pid = process.write_pid_to_file

    async def fail_after_pid_write(path, pid):
        observed["child"] = server.process._process
        observed["log"] = server.process._log_file_handle
        await write_pid(path, pid)
        raise failure_type("Injected PID write failure")

    with monkeypatch.context() as fault:
        fault.setattr(process, "write_pid_to_file", fail_after_pid_write)
        expected = (
            asyncio.CancelledError
            if failure_type is asyncio.CancelledError
            else ServerStartError
        )
        with pytest.raises(expected):
            await server.start()
    assert observed["child"].returncode is not None
    assert observed["log"].closed
    assert server.process._process is None
    assert server.process._log_file_handle is None
    assert not Path(server.get_pid_file_path()).exists()
    assert not server.state.runtime.get_server_runtime(server.server_name).running
    assert not await server.is_running()
    await server.start()
    assert await server.is_running()


async def test_cancel_during_spawn_retains_child_until_cleanup(
    real_bedrock_server, monkeypatch
):
    server = real_bedrock_server
    started, released = asyncio.Event(), asyncio.Event()
    create_process = asyncio.create_subprocess_exec
    observed = {}

    async def gated_spawn(*args, **kwargs):
        child = await create_process(*args, **kwargs)
        observed["child"] = child
        observed["log"] = server.process._log_file_handle
        started.set()
        await released.wait()
        return child

    with monkeypatch.context() as gate:
        gate.setattr(asyncio, "create_subprocess_exec", gated_spawn)
        start = asyncio.create_task(server.start())
        try:
            async with asyncio.timeout(5):
                await started.wait()
                assert observed["child"].returncode is None
                start.cancel()
                released.set()
                with pytest.raises(asyncio.CancelledError):
                    await start
            assert observed["child"].returncode is not None
            assert observed["log"].closed
            assert server.process._process is None
            assert server.process._log_file_handle is None
            assert not Path(server.get_pid_file_path()).exists()
            assert not server.state.runtime.get_server_runtime(
                server.server_name
            ).running
        finally:
            released.set()
            if not start.done():
                start.cancel()
            await asyncio.gather(start, return_exceptions=True)
            child = observed.get("child")
            if child is not None and child.returncode is None:
                child.kill()
                await child.wait()
