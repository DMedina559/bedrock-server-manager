import asyncio

import pytest

from bedrock_server_manager.error import ServerStartError


async def test_server_lifecycle_serializes_starts_and_preserves_command_channel(
    real_bedrock_server,
):
    server = real_bedrock_server
    assert await server.is_installed()
    assert not await server.is_running()
    results = await asyncio.gather(
        server.start(), server.start(), return_exceptions=True
    )
    assert sum(isinstance(result, ServerStartError) for result in results) == 1
    assert sum(result is None for result in results) == 1
    child = server.process._process
    assert child is not None and child.returncode is None
    assert await server.is_running()
    with pytest.raises(ServerStartError):
        await server.start()
    assert server.process._process is child
    await server.send_command("__DUMMY__ PLAYER_JOIN test_user")
    await server.stop()
    assert child.returncode is not None
    assert server.process._process is None
    assert not await server.is_running()


async def test_stopping_stopped_server_is_idempotent(real_bedrock_server):
    assert await real_bedrock_server.stop() is None
    assert await real_bedrock_server.stop() is None


async def test_stale_probe_cannot_replace_newly_started_child(
    real_bedrock_server, monkeypatch
):
    from pathlib import Path

    from bedrock_server_manager.core.server import process as module

    server = real_bedrock_server
    entered, release = asyncio.Event(), asyncio.Event()
    original_verify = module.system_process.get_verified_bedrock_process
    original_write_pid = module.system_process.write_pid_to_file
    probe_task = None

    async def verify(*args, **kwargs):
        if asyncio.current_task() is probe_task:
            entered.set()
            await release.wait()
            return None
        return await original_verify(*args, **kwargs)

    async def write_pid(path, pid):
        release.set()
        assert await probe_task
        await original_write_pid(path, pid)

    monkeypatch.setattr(module.system_process, "write_pid_to_file", write_pid)
    monkeypatch.setattr(module.system_process, "get_verified_bedrock_process", verify)
    probe_task = asyncio.create_task(server.is_running())
    try:
        async with asyncio.timeout(5):
            await entered.wait()
            await server.start()
            child = server.process._process
            release.set()
            assert await probe_task
            assert server.process._process is child
            assert child.returncode is None
            assert Path(server.get_pid_file_path()).exists()
            snapshot = server.state.runtime.get_server_runtime(server.server_name)
            assert snapshot.running and snapshot.pid == child.pid
            with pytest.raises(ServerStartError):
                await server.start()
            await server.send_command("__DUMMY__ PLAYER_JOIN race_test")
            await server.stop()
            assert child.returncode is not None
    finally:
        release.set()
        await asyncio.gather(probe_task, return_exceptions=True)


async def test_start_rollback_retains_spawned_child_when_shared_handle_is_lost(
    real_bedrock_server, monkeypatch
):
    from pathlib import Path

    from bedrock_server_manager.core.server import process as module

    server = real_bedrock_server
    observed = {}

    async def fail_write(*args):
        observed["child"] = server.process._process
        observed["log"] = server.process._log_file_handle
        server.process._process = None
        raise OSError("Injected PID write failure after losing shared handle")

    monkeypatch.setattr(module.system_process, "write_pid_to_file", fail_write)
    with pytest.raises(ServerStartError):
        await server.start()
    assert observed["child"].returncode is not None
    assert observed["log"].closed
    assert not Path(server.get_pid_file_path()).exists()
    assert not await server.is_running()


async def test_recovered_process_exit_is_polled_without_blocking_wait(
    real_bedrock_server,
):
    from unittest.mock import Mock

    import psutil

    recovered = Mock(spec=psutil.Process)
    recovered.is_running.side_effect = [True, False]
    recovered.status.return_value = psutil.STATUS_RUNNING
    await real_bedrock_server.process._wait_for_exit(recovered, 1)
    recovered.wait.assert_not_called()


async def test_recovered_process_exit_polling_times_out(real_bedrock_server):
    from unittest.mock import Mock

    import psutil

    recovered = Mock(spec=psutil.Process)
    recovered.is_running.return_value = True
    recovered.status.return_value = psutil.STATUS_RUNNING
    with pytest.raises(TimeoutError):
        await real_bedrock_server.process._wait_for_exit(recovered, 0.01)
    recovered.wait.assert_not_called()


@pytest.mark.parametrize("missing_pid", [False, True])
async def test_recovered_survivor_stays_outside_monitoring(
    real_bedrock_server, app_context, missing_pid
):
    from pathlib import Path

    from bedrock_server_manager.error import SendCommandError

    server = real_bedrock_server
    await server.start()
    child = server.process._process
    manager = app_context.bedrock_process_manager
    await manager.remove_server(server.server_name)
    server.process._process = None  # Simulate loss of handles across BSM restart.
    if missing_pid:
        Path(server.get_pid_file_path()).unlink()
    try:
        assert await server.is_running()
        assert server.server_name not in manager.servers
        runtime = app_context.state.runtime.get_server_runtime(server.server_name)
        assert runtime.running and runtime.pid == child.pid
        assert runtime.recovered_untracked is missing_pid
        assert not runtime.process_owned
        assert not runtime.command_available
        assert runtime.output_source == "unknown"
        assert not manager.check_health()
        with pytest.raises(SendCommandError):
            await server.send_command("list")
        result = await app_context.api.server.start({"server_name": server.server_name})
        assert result.outcome == "already_running"
        assert server.server_name not in manager.servers
    finally:
        await server.stop()
        await asyncio.wait_for(child.wait(), 5)
    assert (
        app_context.state.runtime.get_server_runtime(
            server.server_name
        ).command_available
        is False
    )


async def test_start_bypasses_negative_discovery_cache(
    real_bedrock_server, app_context
):
    from pathlib import Path

    from bedrock_server_manager.core.bedrock_server import BedrockServer

    owner = real_bedrock_server
    observer = BedrockServer(
        owner.server_name,
        settings=owner.settings,
        events=owner.events,
        state=owner.state,
        storage=owner.storage,
    )
    assert not await observer.is_running()
    assert observer.process._recovery_state.last_negative_scan
    await owner.start()
    Path(owner.get_pid_file_path()).unlink()
    with pytest.raises(ServerStartError, match="already running"):
        await observer.start()
    assert observer.process._process.pid == owner.process._process.pid
    assert observer.process._recovery_state.recovered_pids
