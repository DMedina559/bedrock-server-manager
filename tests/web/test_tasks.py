import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from bedrock_server_manager.api.models import StartServerResponse
from bedrock_server_manager.error import ServerStartError
from bedrock_server_manager.web.tasks import TaskManager


@pytest.fixture
def task_manager(app_context):
    return TaskManager(connection_manager=app_context.connection_manager)


async def test_run_task_success(task_manager):
    def my_task(a, b):
        return a + b

    task_id = await task_manager.run_task(my_task, None, 5, 10)

    # Check immediate status
    assert task_id in task_manager.tasks

    future = task_manager.futures.get(task_id)
    if future:
        await future  # block until done

    # Allow add_done_callback to finish
    await asyncio.sleep(0.01)

    assert task_manager.tasks[task_id]["status"] == "completed"
    assert task_manager.tasks[task_id]["result"] == 15


async def test_model_task_result_is_json_serializable(task_manager):
    async def target():
        return StartServerResponse(
            server_name="example", outcome="started", message="Started"
        )

    task_id = await task_manager.run_task(target)
    await task_manager.futures[task_id]
    await asyncio.sleep(0)
    await asyncio.gather(*task_manager._background_tasks)
    snapshot = await task_manager.get_task(task_id)
    result = snapshot.model_dump(mode="json")["result"]
    assert result["outcome"] == "started"
    assert json.loads(json.dumps(result))["server_name"] == "example"


async def test_task_failure_has_structured_safe_error(task_manager):
    async def target():
        raise ServerStartError("Private path /srv/private")

    task_id = await task_manager.run_task(target)
    with pytest.raises(ServerStartError):
        await task_manager.futures[task_id]
    await asyncio.sleep(0)
    await asyncio.gather(*task_manager._background_tasks)
    details = task_manager.tasks[task_id]
    assert details["status"] == "failed"
    assert details["error"].code == "server_start_failed"
    snapshot = await task_manager.get_task(task_id)
    assert "/srv/private" not in snapshot.model_dump_json()


async def test_run_coroutine_task_success(task_manager, app_context):
    app_context.loop = asyncio.get_running_loop()

    async def my_coro_task(a, b):
        await asyncio.sleep(0.1)
        return a * b

    task_id = await task_manager.run_task(my_coro_task, None, 5, 10)
    assert task_id in task_manager.tasks

    # Wait for the task to complete
    future = task_manager.futures.get(task_id)
    if future:
        await future

    # Allow add_done_callback to finish
    await asyncio.sleep(0.01)

    assert task_manager.tasks[task_id]["status"] == "completed"
    assert task_manager.tasks[task_id]["result"] == 50


async def test_cancel_task(task_manager, app_context):
    app_context.loop = asyncio.get_running_loop()

    async def infinite_task():
        while True:
            await asyncio.sleep(0.1)

    task_id = await task_manager.run_task(infinite_task)
    assert task_id in task_manager.tasks

    # Give it a tiny bit of time to start
    await asyncio.sleep(0.1)

    # Cancel it
    cancel_result = await task_manager.cancel_task(task_id)
    assert cancel_result is True

    # Allow add_done_callback to finish handling the cancellation
    await asyncio.sleep(0.01)

    # Check that status was updated to error (cancelled)
    assert task_manager.tasks[task_id]["status"] == "cancelled"
    assert "cancelled" in task_manager.tasks[task_id]["message"].lower()


async def test_run_task_failure(task_manager):
    def failing_task():
        raise ValueError("Something went wrong")

    task_id = await task_manager.run_task(failing_task)

    future = task_manager.futures.get(task_id)
    if future:
        try:
            await future
        except Exception:
            pass

    # Allow add_done_callback to finish
    await asyncio.sleep(0.01)

    assert task_manager.tasks[task_id]["status"] == "failed"


async def test_run_task_websocket_notification_user_specific(
    task_manager, app_context, monkeypatch
):
    mock_send = MagicMock()

    async def dummy_coro(*args, **kwargs):
        mock_send(*args, **kwargs)

    monkeypatch.setattr(
        app_context.connection_manager,
        "send_to_user",
        AsyncMock(side_effect=dummy_coro),
    )

    # Ensure there is an active loop set for the app context
    app_context.loop = asyncio.get_running_loop()

    def dummy_task():
        return True

    task_id = await task_manager.run_task(dummy_task, username="testuser")

    future = task_manager.futures.get(task_id)
    if future:
        await future

    # Wait for the async task created to execute send_to_user
    await asyncio.sleep(0.1)

    assert mock_send.call_count >= 1


async def test_task_manager_shutdown(task_manager):
    def short_task():
        # Even though we are not using time.sleep in tests where possible,
        # here we want a short task running via to_thread.
        pass

    await task_manager.run_task(short_task)
    await task_manager.shutdown()

    assert task_manager._shutdown_started


async def test_run_task_with_unused_username(task_manager):
    def target_without_username(a, b):
        return a * b

    task_id = await task_manager.run_task(target_without_username, "myuser", 3, 4)

    future = task_manager.futures.get(task_id)
    if future:
        await future

    await asyncio.sleep(0.01)

    assert task_manager.tasks[task_id]["status"] == "completed"
    assert task_manager.tasks[task_id]["result"] == 12
    assert task_manager.tasks[task_id]["username"] == "myuser"


async def test_task_reads_do_not_allow_mutating_live_results(task_manager):
    async def collect():
        return {"nested": {"value": 1}}

    task_id = await task_manager.run_task(collect)
    await task_manager.shutdown()
    snapshots = task_manager.tasks
    snapshots[task_id].result["nested"]["value"] = object()
    snapshots.clear()
    assert task_manager.tasks[task_id].result == {"nested": {"value": 1}}
    public = await task_manager.get_task(task_id)
    public.result["nested"]["value"] = 2
    assert (await task_manager.get_task(task_id)).result == {"nested": {"value": 1}}


async def test_invalid_admission_does_not_evict_completed_task(task_manager):
    from pydantic import ValidationError

    async def collect():
        return None

    task_id = await task_manager.run_task(collect)
    await asyncio.sleep(0.01)
    task_manager._max_tasks = 1
    with pytest.raises(ValidationError):
        await task_manager.run_task(collect, username=42)
    assert task_id in task_manager.tasks
    await task_manager.shutdown()


async def test_slow_notification_does_not_orphan_admission():
    connection = MagicMock(send_to_user=AsyncMock())
    manager = TaskManager(connection)
    admission = asyncio.create_task(manager.run_task(lambda: 1, "owner"))
    task_id = await admission
    assert task_id in manager.futures
    await manager.shutdown()
    assert (await manager.get_task(task_id)).status == "completed"


async def test_cancelled_thread_remains_tracked_until_worker_exits():
    import threading

    started = threading.Event()
    released = threading.Event()
    finished = threading.Event()

    def worker(cancellation_event):
        started.set()
        cancellation_event.wait()
        released.wait()
        finished.set()

    manager = TaskManager(None)
    task_id = await manager.run_task(worker)
    await asyncio.to_thread(started.wait)
    await manager.cancel_task(task_id)
    shutdown = asyncio.create_task(manager.shutdown())
    await asyncio.sleep(0)
    assert not shutdown.done()
    assert (await manager.get_task(task_id)).status == "cancelling"
    released.set()
    await shutdown
    assert finished.is_set()
    assert (await manager.get_task(task_id)).status == "cancelled"
