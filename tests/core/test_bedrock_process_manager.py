import asyncio

import pytest

from bedrock_server_manager.error import FileOperationError, StorageError


async def wait_until(predicate):
    async with asyncio.timeout(10):
        while not predicate():
            await asyncio.sleep(0.01)


async def test_process_manager_add_remove_server(app_context, real_bedrock_server):
    manager = app_context.bedrock_process_manager
    await manager.remove_server(real_bedrock_server.server_name)
    assert real_bedrock_server.server_name not in manager.servers
    await manager.add_server(real_bedrock_server)
    assert manager.servers[real_bedrock_server.server_name] is real_bedrock_server


async def test_process_manager_shutdown_drains_monitor_and_child(
    app_context, real_bedrock_server
):
    manager = app_context.bedrock_process_manager
    await real_bedrock_server.start()
    child = real_bedrock_server.process._process
    await manager.start()
    monitor = manager.monitoring_task
    await manager.shutdown()
    assert monitor.done()
    assert child.returncode is not None
    assert not await real_bedrock_server.is_running()


async def test_restart_attempt_starts_actual_server(app_context, real_bedrock_server):
    await app_context.bedrock_process_manager._try_restart_server(real_bedrock_server)
    assert await real_bedrock_server.is_running()


async def test_restart_limit_persists_error_and_removes_monitoring(
    app_context, real_bedrock_server
):
    await app_context.settings.set("monitoring.max_retries", 0)
    app_context.bedrock_process_manager.restart_attempts[
        real_bedrock_server.server_name
    ] = 1
    manager = app_context.bedrock_process_manager
    await manager._try_restart_server(real_bedrock_server)
    assert real_bedrock_server.server_name not in manager.servers
    assert not await real_bedrock_server.is_running()
    await app_context.reload()
    assert await real_bedrock_server.get_status() == "ERROR"


async def test_error_status_is_persisted(app_context, real_bedrock_server):
    await app_context.bedrock_process_manager.write_error_status(
        real_bedrock_server.server_name
    )
    await app_context.reload()
    assert await real_bedrock_server.get_status() == "ERROR"


async def test_error_status_storage_failure_is_reported(
    app_context, real_bedrock_server, monkeypatch
):
    async def fail_write(*args, **kwargs):
        raise StorageError("write failed")

    with monkeypatch.context() as fault:
        fault.setattr(app_context.storage, "apply_changeset", fail_write)
        with pytest.raises(FileOperationError):
            await app_context.bedrock_process_manager.write_error_status(
                real_bedrock_server.server_name
            )


async def test_monitor_restarts_actual_crashed_child(app_context, real_bedrock_server):
    await app_context.settings.set("monitoring.process_interval_sec", 1)
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


async def test_monitor_player_failure_resets_coherent_runtime(
    app_context, real_bedrock_server, monkeypatch
):
    await app_context.settings.set("monitoring.process_interval_sec", 1)
    await app_context.settings.set("monitoring.player_interval_sec", 1)
    await real_bedrock_server.start()
    real_bedrock_server.players = [{"name": "Alex", "xuid": "1"}]
    scanned = asyncio.Event()

    async def fail_scan():
        scanned.set()
        raise RuntimeError("scan failed")

    manager = app_context.bedrock_process_manager
    with monkeypatch.context() as fault:
        fault.setattr(
            real_bedrock_server.player_tracker, "update_online_players", fail_scan
        )
        await manager.start()
        try:
            await asyncio.wait_for(scanned.wait(), 5)
            assert real_bedrock_server.players == []
            assert real_bedrock_server.player_count == 0
        finally:
            await manager.quiesce()


async def test_probe_failure_does_not_stop_other_servers(
    app_context, real_bedrock_server, monkeypatch
):
    await app_context.settings.set("monitoring.process_interval_sec", 1)
    manager = app_context.bedrock_process_manager
    other = app_context.get_server("other")
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
