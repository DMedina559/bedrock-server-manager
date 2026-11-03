"""Fault and protocol regressions for owned BDS output, not file polling."""

import asyncio
import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from bedrock_server_manager.core.server.runtime import (
    OwnedBDSRun,
    PlayerIdentityWriter,
    validate_command,
)
from bedrock_server_manager.error import SendCommandError, ServerProcessError
from bedrock_server_manager.state.models import RuntimeState


def make_server():
    async def set_status(status):
        pass

    return SimpleNamespace(
        server_name="runtime",
        process=SimpleNamespace(run=None),
        _runtime_state=RuntimeState(),
        settings=SimpleNamespace(get=lambda key, default=None: default),
        identity_writer=None,
        storage=None,
        events=None,
        set_status_in_config=set_status,
    )


def make_run(tmp_path):
    server = make_server()
    child = Mock(spec=asyncio.subprocess.Process)
    child.pid = os.getpid()
    child.returncode = None
    child.stdin = Mock()
    child.stdin.is_closing.return_value = False
    child.stdin.drain = AsyncMock()
    child.wait = AsyncMock()
    log = (tmp_path / "output.log").open("ab")
    run = OwnedBDSRun(server, child, str(tmp_path / "output.log"), log, lambda _: None)
    server.process.run = run
    server.send_command = run.send
    return run


@pytest.mark.parametrize(
    "text", ["say hi\nstop", "stop\rlist", "say\x00test", "say\u2028stop", "x" * 65537]
)
def test_commands_reject_protocol_delimiters_and_oversize(text):
    with pytest.raises(SendCommandError):
        validate_command(text)


async def test_command_drain_has_deadline_and_releases_writer(tmp_path):
    run = make_run(tmp_path)
    gate = asyncio.Event()
    run.process.stdin.drain = gate.wait
    try:
        with pytest.raises(SendCommandError, match="uncertain"):
            await run.send("list", timeout=0.01)
        assert not run._write_lock.locked()
        gate.set()
        await run.send("list", timeout=0.1)
    finally:
        run.log_file.close()


async def test_parser_orders_presence_waits_and_complete_save_frames(tmp_path):
    run = make_run(tmp_path)
    identities = []
    run.server.identity_writer = SimpleNamespace(
        submit=lambda name, xuid: identities.append((name, xuid))
    )
    try:
        waiter = run.watch("Player connected")
        run.feed(b"[INFO] Player connected: Test, xuid: 12\r")
        assert not waiter.done()
        run.feed(b"\n[INFO] Player disconnected: Test, xuid: 12\n")
        assert (await waiter).sequence == 1
        assert not run.players
        assert identities == [("Test", "12")]
        future = asyncio.get_running_loop().create_future()
        run._save_future = future
        run.feed(b"Data saved. Files are now ready to be copied.\nworld/db/one:1, wor")
        assert not future.done()
        run.feed(b"ld/db/two:2\nworld/level.dat:3\n")
        assert (
            not future.done()
        )  # A first file/line cannot terminate a multiline frame.
        run.feed(b"Data saved. Files are now ready to be copied.\n")
        assert await future == [
            ("world/db/one", 1),
            ("world/db/two", 2),
            ("world/level.dat", 3),
        ]
    finally:
        run.log_file.close()


async def test_wait_cancellation_exit_and_generation_boundaries(tmp_path):
    run = make_run(tmp_path)
    try:
        task = asyncio.create_task(run.wait_for_log("never", timeout=1))
        await asyncio.sleep(0)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        assert not run._waiters
        waiter = run.watch("never")
        run._fail_waiters("Process exited")
        with pytest.raises(ServerProcessError):
            await waiter
        run.server.process.run = None
        with pytest.raises(SendCommandError):
            await run.send("list")
    finally:
        run.log_file.close()


async def test_identity_worker_retains_uncommitted_batch_and_newer_names():
    entered, release = asyncio.Event(), asyncio.Event()

    async def save(batch):
        entered.set()
        await release.wait()

    storage = SimpleNamespace(save_players=AsyncMock(side_effect=save))
    writer = PlayerIdentityWriter(storage)
    writer.pending["12"] = "Before"
    task = asyncio.create_task(writer.flush())
    await entered.wait()
    writer.pending["12"] = "After"
    release.set()
    await task
    assert writer.pending == {"12": "After"}
    storage.save_players = AsyncMock(side_effect=OSError("disk full"))
    with pytest.raises(OSError):
        await writer.flush()
    assert writer.pending == {"12": "After"}
    storage.save_players = AsyncMock(return_value=1)
    await writer.shutdown()
    assert not writer.pending


async def test_native_pipe_flood_drains_before_exit_and_preserves_raw_history(tmp_path):
    server = make_server()
    content = b"[INFO] ordinary output \xc3\xa9\r\n" * 12000
    child = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        "import sys; sys.stdout.buffer.write(bytes.fromhex(sys.argv[1])*12000); sys.stdout.flush()",
        (b"[INFO] ordinary output \xc3\xa9\r\n").hex(),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    # Use a bounded command argument and ask the child to generate the burst itself.
    log = (tmp_path / "flood.log").open("ab")
    run = OwnedBDSRun(server, child, str(tmp_path / "flood.log"), log, lambda _: None)
    server.process.run = run
    run.start()
    try:
        await asyncio.wait_for(run.closed.wait(), 10)
        assert (tmp_path / "flood.log").read_bytes() == content
        assert run.dropped_bytes == 0
        assert run.reader_done.is_set()
        assert not run._waiters
    finally:
        if child.returncode is None:
            child.kill()
            await child.wait()
        await asyncio.gather(*run.tasks, return_exceptions=True)


async def test_delayed_metrics_cannot_resurrect_exited_run(
    real_bedrock_server, monkeypatch
):
    from bedrock_server_manager.core.server import process as module

    server = real_bedrock_server
    await server.start()
    started, release = asyncio.Event(), asyncio.Event()
    original = module.run_in_thread

    async def delayed(target, *args, **kwargs):
        if target == server.process._resource_monitor.get_stats:
            started.set()
            await release.wait()
            return {
                "pid": old_pid,
                "cpu_percent": 1,
                "memory_mb": 1,
                "uptime": "0:00:01",
            }
        return await original(target, *args, **kwargs)

    old_pid = server.process._process.pid
    monkeypatch.setattr(module, "run_in_thread", delayed)
    sample = asyncio.create_task(server.get_process_info())
    await started.wait()
    await server.stop()
    release.set()
    assert await sample is None
    assert not server._runtime_state.get_server_runtime(server.server_name).running


async def test_plugin_log_wait_is_cancelled_when_owner_deactivates(
    real_bedrock_server, app_context
):
    from bedrock_server_manager.api.models.server import WaitForServerLogRequest
    from bedrock_server_manager.api.server import wait_for_server_log

    server = real_bedrock_server
    await server.start()
    owner = "plugin:output-wait-test"
    app_context.events.activate_owner(owner)
    task = asyncio.create_task(
        wait_for_server_log(
            WaitForServerLogRequest(
                server_name=server.server_name, text="never emitted", timeout=10
            ),
            app_context=app_context,
            plugin_name="output-wait-test",
        )
    )
    async with asyncio.timeout(5):
        while not server.process.run._waiters:
            await asyncio.sleep(0)
    app_context.events.deactivate_owner(owner)
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not server.process.run._waiters


async def test_stop_escalation_keeps_reader_alive_and_finishes_cleanup(
    real_bedrock_server, monkeypatch
):
    import time

    from bedrock_server_manager.core.server import process as module

    original_spawn = asyncio.create_subprocess_exec

    async def spawn(*args, **kwargs):
        return await original_spawn(
            sys.executable,
            "-u",
            "-c",
            "import time; print('Server started.',flush=True);\nwhile True: print('ordinary output',flush=True); time.sleep(.005)",
            **kwargs,
        )

    server = real_bedrock_server
    monkeypatch.setattr(module.asyncio, "create_subprocess_exec", spawn)
    await server.settings.set("lifecycle.server_stop_timeout_seconds", 0.5)
    await server.start()
    run = server.process.run
    await asyncio.wait_for(run.ready_event.wait(), 5)
    started = time.monotonic()
    await server.stop()
    assert time.monotonic() - started < 4
    assert run.process.returncode is not None
    assert run.reader_done.is_set()
    assert run.exit_reason in {"terminated", "killed"}
    assert run.log_file.closed
    assert not server._runtime_state.get_server_runtime(server.server_name).running


async def test_reducer_failure_still_drains_pipe_during_controlled_stop(tmp_path):
    server = make_server()

    def unavailable(*args):
        raise RuntimeError("identity capacity")

    server.identity_writer = SimpleNamespace(submit=unavailable)
    code = (
        "import sys; print('Player connected: Test, xuid: 12',flush=True); "
        "sys.stdout.write('ordinary output\\n'*100000); sys.stdout.flush(); "
        "sys.stdin.readline()"
    )
    child = await asyncio.create_subprocess_exec(
        sys.executable,
        "-u",
        "-c",
        code,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    log = (tmp_path / "failed.log").open("ab")
    run = OwnedBDSRun(server, child, str(tmp_path / "failed.log"), log, lambda _: None)
    server.process.run = run
    server.send_command = run.send
    run.start()
    try:
        await asyncio.wait_for(run.closed.wait(), 10)
        assert child.returncode is not None
        assert run.failure and "RuntimeError" in run.failure
        assert run.reader_done.is_set()
    finally:
        if child.returncode is None:
            child.kill()
            await child.wait()
        await asyncio.gather(*run.tasks, return_exceptions=True)
        for task in (run._failure_task, run._stop_task):
            if task is not None:
                await asyncio.gather(task, return_exceptions=True)
