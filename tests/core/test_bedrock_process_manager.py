import asyncio

import pytest

from bedrock_server_manager.error import FileOperationError, StorageError


async def wait_until(predicate):
    async with asyncio.timeout(10):
        while not predicate():
            await asyncio.sleep(0.01)


async def test_process_manager_add_remove_error_status_and_restart_limits(
    app_context, real_bedrock_server, monkeypatch
):
    manager = app_context.bedrock_process_manager
    await manager.remove_server(real_bedrock_server.server_name)
    assert real_bedrock_server.server_name not in manager.servers
    await manager.add_server(real_bedrock_server)
    assert manager.servers[real_bedrock_server.server_name] is real_bedrock_server

    # Error status persisted and storage failure reported
    await manager.write_error_status(real_bedrock_server.server_name)
    await app_context.reload()
    assert await real_bedrock_server.get_status() == "ERROR"

    async def fail_write(*args, **kwargs):
        raise StorageError("write failed")

    with monkeypatch.context() as fault:
        fault.setattr(app_context.storage, "commit_record", fail_write)
        with pytest.raises(FileOperationError):
            await manager.write_error_status(real_bedrock_server.server_name)

    # Restart limit persists error and removes monitoring
    await app_context.settings.set("monitoring.max_retries", 0)
    manager.restart_attempts[real_bedrock_server.server_name] = 1
    await manager._try_restart_server(real_bedrock_server)
    assert real_bedrock_server.server_name not in manager.servers
    assert not await real_bedrock_server.is_running()
    await app_context.reload()
    assert await real_bedrock_server.get_status() == "ERROR"

    # Restart attempt starts actual server when within retries
    await app_context.settings.set("monitoring.max_retries", 3)
    manager.restart_attempts[real_bedrock_server.server_name] = 0
    await manager.add_server(real_bedrock_server)
    await manager._try_restart_server(real_bedrock_server)
    assert await real_bedrock_server.is_running()

    # Shutdown drains monitor and child
    child = real_bedrock_server.process._process
    await manager.start()
    monitor = manager.monitoring_task
    await manager.shutdown()
    assert monitor.done()
    assert child.returncode is not None
    assert not await real_bedrock_server.is_running()


async def test_monitor_restarts_crashed_child_and_isolates_failures(
    app_context, real_bedrock_server, monkeypatch
):
    await app_context.settings.set("monitoring.process_interval_sec", 1)
    await app_context.settings.set("monitoring.player_interval_sec", 1)
    await real_bedrock_server.start()
    child = real_bedrock_server.process._process
    child.kill()
    await child.wait()
    manager = app_context.bedrock_process_manager
    await manager.start()
    try:
        await wait_until(
            lambda: real_bedrock_server.process._process is not None
            and real_bedrock_server.process._process is not child
            and real_bedrock_server.process._process.returncode is None
        )
        assert manager.restart_attempts[real_bedrock_server.server_name] == 1
    finally:
        await manager.quiesce()

    # Player failure retains last known runtime
    manager._stopping = False
    real_bedrock_server.players = [{"name": "Alex", "xuid": "1"}]
    scanned = asyncio.Event()

    async def fail_scan():
        scanned.set()
        raise RuntimeError("scan failed")

    with monkeypatch.context() as fault:
        fault.setattr(
            real_bedrock_server.player_tracker, "update_online_players", fail_scan
        )
        await manager.start()
        try:
            await asyncio.wait_for(scanned.wait(), 5)
            assert real_bedrock_server.players == [{"name": "Alex", "xuid": "1"}]
            assert real_bedrock_server.player_count == 1
            assert not real_bedrock_server.state.runtime.get_server_runtime(
                real_bedrock_server.server_name
            ).players_available
        finally:
            await manager.quiesce()

    # Probe failure does not stop other servers
    manager._stopping = False
    other = app_context.prepare_server("other")
    other.process.intentionally_stopped = True
    await manager.add_server(other)

    async def fail_probe():
        raise RuntimeError("probe failed")

    with monkeypatch.context() as fault:
        fault.setattr(real_bedrock_server, "is_running", fail_probe)
        await manager.start()
        try:
            await wait_until(lambda: "other" not in manager.servers)
            assert real_bedrock_server.server_name in manager.servers
        finally:
            await manager.quiesce()
