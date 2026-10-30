"""Avoid duplicate capture reads while retaining integrity and bounded hooks."""

import asyncio
import hashlib
import threading
from pathlib import Path

import pytest

from bedrock_server_manager.backups import server as capture
from bedrock_server_manager.events import EventBus, EventDefinition, EventOptions
from bedrock_server_manager.events.control import CancellableEvent
from bedrock_server_manager.utils.threads import run_in_thread, worker_snapshot


def test_copied_files_do_not_need_second_hash_read(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    (source / "nested").mkdir()
    payloads = {"level.dat": b"world", "nested/pack": b"x" * (1024 * 1024 + 5)}
    for name, data in payloads.items():
        (source / name).write_bytes(data)
    hashes = {}
    staging = tmp_path / "staging"
    capture.copy_source(source, staging / "world", hashes=hashes)

    def no_second_read(*args, **kwargs):
        pytest.fail("Copied data must not be read again for inventory hashing")

    monkeypatch.setattr(capture, "digest", no_second_read)
    files, directories = capture.inventory(
        staging, {"world": "included"}, hashes=hashes
    )
    assert "world/nested" in directories
    assert len(files) == len(payloads)
    for file in files:
        data = payloads[file.path.removeprefix("world/")]
        assert file.sha256 == hashlib.sha256(data).hexdigest()
        assert file.size == len(data)


def test_changed_or_uncached_staging_files_are_hashed(tmp_path):
    source = tmp_path / "level.dat"
    source.write_bytes(b"old")
    staging = tmp_path / "staging"
    hashes = {}
    target = staging / "world" / "level.dat"
    capture.copy_source(source, target, hashes=hashes)
    target.write_bytes(b"new content")
    (target.parent / "live-file").write_bytes(b"uncached")
    files, _ = capture.inventory(staging, {"world": "included"}, hashes=hashes)
    assert {f.path: f.sha256 for f in files} == {
        "world/level.dat": hashlib.sha256(b"new content").hexdigest(),
        "world/live-file": hashlib.sha256(b"uncached").hexdigest(),
    }


async def test_cancelled_worker_does_not_emit_unhandled_shield_error():
    loop = asyncio.get_running_loop()
    original = loop.get_exception_handler()
    errors = []
    loop.set_exception_handler(lambda loop, context: errors.append(context))
    entered = threading.Event()

    def worker(cancellation_event):
        entered.set()
        cancellation_event.wait(3)
        raise InterruptedError("Worker cancellation requested.")

    task = asyncio.create_task(run_in_thread(worker))
    try:
        assert await asyncio.to_thread(entered.wait, 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        await asyncio.sleep(0)
        assert worker_snapshot()["draining"] == 0
        assert not errors
    finally:
        loop.set_exception_handler(original)


@pytest.mark.parametrize("timeout", [0, -1, True, float("inf"), float("nan"), 3601])
def test_listener_budget_rejects_invalid_values(timeout):
    bus = EventBus()
    with pytest.raises(ValueError):
        bus.subscribe("sample", lambda **kwargs: None, timeout_seconds=timeout)


async def test_listener_budget_is_local_to_subscription():
    bus = EventBus(EventOptions(hook_timeout_seconds=0.005))
    bus.registry.register(EventDefinition(name="before_demo", phase="before"))

    async def slow(**kwargs):
        await asyncio.sleep(0.02)

    bus.subscribe("before_demo", slow, timeout_seconds=0.2)
    control = CancellableEvent()
    result = await bus.emit("before_demo", {"event": control})
    assert not result.failures and not control.is_cancelled
    bus.subscribe("before_demo", slow, listener_id="default-budget")
    control = CancellableEvent()
    result = await bus.emit("before_demo", {"event": control})
    assert control.is_cancelled
    assert result.failures[0].code == "event_listener_timeout"


@pytest.mark.parametrize("required", [False, True])
async def test_pre_start_backup_timeout_respects_requirement(
    populated_server, plugin_factory, app_context, monkeypatch, required
):
    source = (
        Path(__file__).parents[2]
        / "src/bedrock_server_manager/plugins/default/backup_on_start.py"
    )
    plugin = await plugin_factory("backup_on_start", source.read_text())
    await plugin.set_plugin_setting("timeout_seconds", 0.01)
    await plugin.set_plugin_setting("require_complete_backup", required)
    app_context.events.options.hook_timeout_seconds = 0.001

    async def stalled(**kwargs):
        await kwargs["progress"]("Capturing server files")
        await asyncio.Event().wait()

    monkeypatch.setattr(populated_server.backups, "_create_snapshot", stalled)
    from bedrock_server_manager.api.models import StartServerRequest

    control = CancellableEvent()
    async with asyncio.timeout(2):
        result = await app_context.events.emit(
            "before_server_start",
            {
                "server_name": populated_server.server_name,
                "request": StartServerRequest(server_name=populated_server.server_name),
                "event": control,
            },
        )
    assert control.is_cancelled is required
    assert not result.failures


@pytest.mark.parametrize("mode", ["world", "selected", "full"])
async def test_optimized_capture_still_verifies(populated_server, mode):
    backup = await populated_server.backups.create_snapshot(mode=mode)
    verified = await populated_server.backups.verify_snapshot(backup.backup_id)
    assert verified.status == "verified"
