import asyncio

import pytest

from bedrock_server_manager.api.models import StartServerResponse
from bedrock_server_manager.web.tasks import TaskManager
from bedrock_server_manager.web.websocket_manager import ConnectionManager


async def test_task_owner_and_disconnected_notification():
    connection = ConnectionManager()
    manager = TaskManager(connection)

    async def operation():
        return StartServerResponse(
            server_name="example", outcome="started", message="Started"
        )

    task_id = await manager.run_task(operation, "owner")
    await manager.shutdown()
    snapshot = await manager.get_task(task_id, username="owner")
    assert snapshot.status == "completed"
    assert snapshot.result["outcome"] == "started"
    assert await manager.get_task(task_id, username="other") is None
    assert await manager.get_all_tasks(username="other") == {}


async def test_active_task_capacity_preserves_running_handle():
    manager = TaskManager(None)
    manager._max_tasks = 1
    gate = asyncio.Event()
    task_id = await manager.run_task(gate.wait)
    with pytest.raises(RuntimeError):
        await manager.run_task(gate.wait)
    assert task_id in manager.futures
    gate.set()
    await manager.shutdown()


async def test_invalid_task_output_is_an_internal_error():
    manager = TaskManager(None)

    async def operation():
        return object()

    task_id = await manager.run_task(operation)
    await manager.shutdown()
    snapshot = await manager.get_task(task_id)
    assert snapshot.status == "failed"
    assert snapshot.result is None
    assert snapshot.error.code == "internal_error"
