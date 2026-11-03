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
    assert real_bedrock_server.server_name in manager.recovery_failures
    assert not manager.check_health()
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
    from bedrock_server_manager.core.server.process import system_process

    publishing_pid = asyncio.Event()
    release_pid = asyncio.Event()
    write_pid = system_process.write_pid_to_file

    async def pause_pid_publication(*args, **kwargs):
        publishing_pid.set()
        await release_pid.wait()
        return await write_pid(*args, **kwargs)

    with monkeypatch.context() as startup:
        startup.setattr(system_process, "write_pid_to_file", pause_pid_publication)
        await manager.start()
        try:
            await asyncio.wait_for(publishing_pid.wait(), 10)
            replacement = real_bedrock_server.process._process
            assert replacement is not None and replacement is not child
            assert replacement.returncode is None
            recovery = manager._server_checks[real_bedrock_server.server_name]
            assert not recovery.done()
            # A published process handle is not a completed start. Quiescing here
            # cancels PID/state publication and correctly rolls the child back.
            release_pid.set()
            await asyncio.wait_for(asyncio.shield(recovery), 10)
            assert await real_bedrock_server.is_running()
            assert await real_bedrock_server.get_status() == "RUNNING"
            assert manager.restart_attempts[real_bedrock_server.server_name] == 1
        finally:
            release_pid.set()
            await manager.quiesce()

    # Player failure retains last known runtime
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


async def test_process_manager_check_health(app_context):
    """Test health checking logic of BedrockProcessManager."""
    manager = app_context.bedrock_process_manager
    assert manager.check_health() is True
    srv = "untracked_recovered_server"
    app_context.state.runtime.update_server_runtime(srv, running=True, pid=123)
    assert manager.check_health() is False
    app_context.state.runtime.update_server_runtime(srv, running=False, pid=None)
    assert manager.check_health() is True

    # Exceeded restart retries marks it unhealthy
    manager.restart_attempts[srv] = 10
    try:
        assert manager.check_health() is False
    finally:
        manager.restart_attempts.clear()
    assert manager.check_health() is True

    # Done monitoring task without shutdown marks it unhealthy
    dummy_task = asyncio.create_task(asyncio.sleep(0))
    await dummy_task
    manager.monitoring_task = dummy_task
    try:
        assert manager.check_health() is False
        # Shutdown suppresses failure
        manager._shutdown_event.set()
        assert manager.check_health() is True
    finally:
        manager._shutdown_event.clear()
        manager.monitoring_task = None
    assert manager.check_health() is True


async def test_successful_recovery_clears_health_after_stable_running(
    real_bedrock_server, app_context
):
    import time

    server = real_bedrock_server
    await server.start()
    manager = app_context.bedrock_process_manager
    manager.restart_attempts[server.server_name] = 1
    manager._healthy_since[server.server_name] = time.monotonic() - 60
    assert not manager.check_health()
    await manager._observe_server(server.server_name, server, scan_players=False)
    assert server.server_name not in manager.restart_attempts
    assert manager.check_health()
