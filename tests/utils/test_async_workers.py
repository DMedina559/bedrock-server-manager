"""Responsiveness and ownership at synchronous worker boundaries."""

import asyncio
import io
import threading

import pytest

from bedrock_server_manager.utils.io import temporary_directory
from bedrock_server_manager.utils.threads import (
    copy_stream,
    run_in_thread,
    worker_snapshot,
)


async def test_cancellation_keeps_worker_owned_until_cleanup_finishes():
    loop = asyncio.get_running_loop()
    entered, cancelled = asyncio.Event(), asyncio.Event()
    release = threading.Event()

    def operation(cancellation_event=None):
        loop.call_soon_threadsafe(entered.set)
        assert cancellation_event.wait(5)
        loop.call_soon_threadsafe(cancelled.set)
        assert release.wait(5)

    task = asyncio.create_task(run_in_thread(operation))
    try:
        await asyncio.wait_for(entered.wait(), 2)
        assert worker_snapshot()["running"] == 1
        task.cancel()
        await asyncio.wait_for(cancelled.wait(), 2)
        task.cancel()  # A repeated cancellation must not detach the thread.
        await asyncio.sleep(0)
        assert not task.done()
        assert worker_snapshot()["draining"] == 1
        assert worker_snapshot()["oldest_draining_seconds"] is not None
    finally:
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
    await asyncio.sleep(0)
    assert worker_snapshot()["running"] == worker_snapshot()["draining"] == 0


async def test_staging_cleanup_runs_outside_event_loop(tmp_path, monkeypatch):
    from bedrock_server_manager.utils import io as files

    loop = asyncio.get_running_loop()
    entered = asyncio.Event()
    release = threading.Event()
    remove = files.shutil.rmtree
    owner = threading.get_ident()

    def cleanup(path):
        assert threading.get_ident() != owner
        loop.call_soon_threadsafe(entered.set)
        assert release.wait(5)
        remove(path)

    monkeypatch.setattr(files.shutil, "rmtree", cleanup)
    paths = []

    async def operation():
        async with temporary_directory(tmp_path) as path:
            paths.append(path)
            (path / "world.db").write_bytes(b"world")

    task = asyncio.create_task(operation())
    try:
        await asyncio.wait_for(entered.wait(), 2)
        assert not task.done()
        assert paths[0].exists()
    finally:
        release.set()
        await task
    assert not paths[0].exists()


def test_copy_checks_cancellation_before_writing_next_chunk():
    cancelled = threading.Event()

    class Source(io.BytesIO):
        def read(self, size=-1):
            data = super().read(size)
            cancelled.set()
            return data

    target = io.BytesIO()
    with pytest.raises(InterruptedError):
        copy_stream(Source(b"unpublished"), target, cancelled)
    assert target.getvalue() == b""


@pytest.mark.parametrize("helper", ["verify", "hash"])
async def test_password_work_is_bounded_and_does_not_block_loop(monkeypatch, helper):
    from bedrock_server_manager.web import auth

    loop = asyncio.get_running_loop()
    entered = asyncio.Event()
    release = threading.Event()
    workers = set()
    owner = threading.get_ident()

    def operation(*args):
        workers.add(threading.get_ident())
        if len(workers) == 4:
            loop.call_soon_threadsafe(entered.set)
        assert release.wait(5)
        return True if helper == "verify" else "hashed"

    monkeypatch.setattr(
        auth,
        "verify_password" if helper == "verify" else "get_password_hash",
        operation,
    )
    tasks = [
        asyncio.create_task(
            auth.verify_password_async("password", "hash")
            if helper == "verify"
            else auth.get_password_hash_async("password")
        )
        for _ in range(6)
    ]
    try:
        await asyncio.wait_for(entered.wait(), 2)
        assert owner not in workers
        assert len(workers) == 4
        assert all(not task.done() for task in tasks)
    finally:
        release.set()
        await asyncio.gather(*tasks)


async def test_worker_preserves_explicit_cancellation_token():
    token = threading.Event()

    def operation(cancellation_event):
        return cancellation_event is token

    assert await run_in_thread(operation, token)
    assert await run_in_thread(operation, cancellation_event=token)


async def test_positional_only_worker_parameter_remains_supported():
    def operation(cancellation_event=None, /):
        return cancellation_event

    assert await run_in_thread(operation) is None
