import asyncio
import time
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

    # We will use purely synchronous checking to bypass issues with how asyncio test scopes
    # interact with the ThreadPoolExecutor's event loop references.

    task_id = task_manager.run_task(my_task, None, 5, 10)

    # Check immediate status
    assert task_id in task_manager.tasks

    future = task_manager.futures.get(task_id)
    if future:
        future.result()  # block until done

    time.sleep(0.1)  # allow thread pool callbacks to finish

    assert task_manager.tasks[task_id]["status"] == "success"
    assert task_manager.tasks[task_id]["result"] == 15


@pytest.mark.asyncio
async def test_run_task_failure(task_manager):
    def failing_task():
        raise ValueError("Something went wrong")

    task_id = task_manager.run_task(failing_task)

    future = task_manager.futures.get(task_id)
    if future:
        try:
            future.result()
        except Exception:
            pass

    time.sleep(0.1)

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
        future.result()

    # Wait for the async run_coroutine_threadsafe to actually execute in the loop
    await asyncio.sleep(0.1)

    assert mock_send.call_count >= 1


def test_task_manager_shutdown(task_manager):
    def infinite_task():
        time.sleep(0.1)

    task_manager.run_task(infinite_task)
    task_manager.shutdown()

    assert task_manager._shutdown_started
