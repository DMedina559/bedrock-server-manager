import asyncio
from unittest.mock import MagicMock

import pytest

from bedrock_server_manager.web.tasks import TaskManager


@pytest.fixture
def task_manager(app_context):
    return TaskManager(app_context)


@pytest.mark.asyncio
async def test_run_task_success(task_manager):
    def my_task(a, b):
        return a + b

    task_id = task_manager.run_task(my_task, None, 5, 10)

    # Check immediate status
    assert task_id in task_manager.tasks

    future = task_manager.futures.get(task_id)
    if future:
        await future  # block until done

    # Allow add_done_callback to finish
    await asyncio.sleep(0.01)

    assert task_manager.tasks[task_id]["status"] == "success"
    assert task_manager.tasks[task_id]["result"] == 15


@pytest.mark.asyncio
async def test_run_async_task_success(task_manager, app_context):
    app_context.loop = asyncio.get_running_loop()

    async def my_async_task(a, b):
        await asyncio.sleep(0.1)
        return a * b

    task_id = task_manager.run_task(my_async_task, None, 5, 10)
    assert task_id in task_manager.tasks

    # Wait for the task to complete
    future = task_manager.futures.get(task_id)
    if future:
        await future

    # Allow add_done_callback to finish
    await asyncio.sleep(0.01)

    assert task_manager.tasks[task_id]["status"] == "success"
    assert task_manager.tasks[task_id]["result"] == 50


@pytest.mark.asyncio
async def test_cancel_task(task_manager, app_context):
    app_context.loop = asyncio.get_running_loop()

    async def infinite_task():
        while True:
            await asyncio.sleep(0.1)

    task_id = task_manager.run_task(infinite_task)
    assert task_id in task_manager.tasks

    # Give it a tiny bit of time to start
    await asyncio.sleep(0.1)

    # Cancel it
    assert task_manager.cancel_task(task_id) is True

    # Allow add_done_callback to finish handling the cancellation
    await asyncio.sleep(0.01)

    # Check that status was updated to error (cancelled)
    assert task_manager.tasks[task_id]["status"] == "error"
    assert "cancelled" in task_manager.tasks[task_id]["message"].lower()


@pytest.mark.asyncio
async def test_run_task_failure(task_manager):
    def failing_task():
        raise ValueError("Something went wrong")

    task_id = task_manager.run_task(failing_task)

    future = task_manager.futures.get(task_id)
    if future:
        try:
            await future
        except Exception:
            pass

    # Allow add_done_callback to finish
    await asyncio.sleep(0.01)

    assert task_manager.tasks[task_id]["status"] == "error"


@pytest.mark.asyncio
async def test_run_task_websocket_notification_user_specific(
    task_manager, app_context, monkeypatch
):
    mock_send = MagicMock()

    async def dummy_coro(*args, **kwargs):
        mock_send(*args, **kwargs)

    monkeypatch.setattr(
        app_context.connection_manager,
        "send_to_user",
        MagicMock(return_value=dummy_coro()),
    )

    # Ensure there is an active loop set for the app context
    app_context.loop = asyncio.get_running_loop()

    def dummy_task():
        return True

    task_id = task_manager.run_task(dummy_task, username="testuser")

    future = task_manager.futures.get(task_id)
    if future:
        await future

    # Wait for the async task created to execute send_to_user
    await asyncio.sleep(0.1)

    assert mock_send.call_count >= 1


@pytest.mark.asyncio
async def test_task_manager_shutdown(task_manager):
    def short_task():
        # Even though we are not using time.sleep in tests where possible,
        # here we want a short task running via to_thread.
        pass

    task_manager.run_task(short_task)
    await task_manager.shutdown()

    assert task_manager._shutdown_started
