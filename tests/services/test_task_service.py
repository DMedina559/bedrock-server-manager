import asyncio
import json

import pytest
import pytest_asyncio

from bedrock_server_manager.api.models import StartServerResponse
from bedrock_server_manager.error import OperationConflictError, ServerStartError
from bedrock_server_manager.services.task_service import TaskManager
from bedrock_server_manager.web.websocket_manager import ConnectionManager


@pytest_asyncio.fixture
async def task_manager(app_context):
    manager = TaskManager(connection_manager=app_context.connection_manager)
    try:
        yield manager
    finally:
        for future in list(manager.futures.values()):
            if not future.done():
                future.cancel()
        async with asyncio.timeout(5):
            await manager.shutdown()


async def finish_task(manager, task_id):
    async with asyncio.timeout(5):
        future = manager.futures.get(task_id)
        if future is not None:
            await asyncio.gather(future, return_exceptions=True)
        await asyncio.sleep(0)
        while manager._background_tasks:
            updates = list(manager._background_tasks)
            await asyncio.gather(*updates)
            manager._background_tasks.difference_update(updates)
        snapshot = await manager.get_task(task_id)
        assert snapshot.status in {"completed", "failed", "cancelled"}
        return snapshot


async def test_run_task_success(task_manager):
    def my_task(a, b):
        return a + b

    task_id = await task_manager.run_task(my_task, None, 5, 10)

    # Check immediate status
    assert task_id in task_manager.tasks

    await finish_task(task_manager, task_id)

    assert task_manager.tasks[task_id]["status"] == "completed"
    assert task_manager.tasks[task_id]["result"] == 15


async def test_model_task_result_is_json_serializable(task_manager):
    async def target():
        return StartServerResponse(
            server_name="example", outcome="started", message="Started"
        )

    task_id = await task_manager.run_task(target)
    snapshot = await finish_task(task_manager, task_id)
    result = snapshot.model_dump(mode="json")["result"]
    assert result["outcome"] == "started"
    assert json.loads(json.dumps(result))["server_name"] == "example"


async def test_task_failure_has_structured_safe_error(task_manager):
    async def target():
        raise ServerStartError("Private path /srv/private")

    task_id = await task_manager.run_task(target)
    await finish_task(task_manager, task_id)
    details = task_manager.tasks[task_id]
    assert details["status"] == "failed"
    assert details["error"].code == "server_start_failed"
    snapshot = await task_manager.get_task(task_id)
    assert "/srv/private" not in snapshot.model_dump_json()


async def test_run_coroutine_task_success(task_manager):
    started, released = asyncio.Event(), asyncio.Event()

    async def multiply(a, b):
        started.set()
        await released.wait()
        return a * b

    task_id = await task_manager.run_task(multiply, None, 5, 10)
    async with asyncio.timeout(5):
        await started.wait()
    assert (await task_manager.get_task(task_id)).status == "running"
    released.set()
    snapshot = await finish_task(task_manager, task_id)
    assert snapshot.status == "completed"
    assert snapshot.result == 50


async def test_cancel_task(task_manager):
    started, cleaned_up = asyncio.Event(), asyncio.Event()

    async def wait_forever():
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cleaned_up.set()

    task_id = await task_manager.run_task(wait_forever)
    async with asyncio.timeout(5):
        await started.wait()
        assert await task_manager.cancel_task(task_id)
        await cleaned_up.wait()
    snapshot = await finish_task(task_manager, task_id)
    assert snapshot.status == "cancelled"
    assert "cancelled" in snapshot.message.lower()
    assert task_id not in task_manager.futures


async def test_run_task_failure(task_manager):
    def failing_task():
        raise ValueError("Something went wrong")

    task_id = await task_manager.run_task(failing_task)
    snapshot = await finish_task(task_manager, task_id)
    assert snapshot.status == "failed"
    assert snapshot.error is not None


async def test_run_task_websocket_notification_user_specific(
    app_context, subscribed_socket, test_admin_user
):
    async with subscribed_socket() as socket:
        task_id = await app_context.task_manager.run_task(
            lambda: True, username=test_admin_user.username
        )
        async with asyncio.timeout(5):
            while True:
                message = json.loads(await socket.recv())
                if (
                    message.get("topic") == f"task:{task_id}"
                    and message["data"]["status"] == "completed"
                ):
                    break
        assert message["type"] == "task_update"
        assert message["data"]["result"] is True
        assert "username" not in message["data"]


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

    await finish_task(task_manager, task_id)

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
    await finish_task(task_manager, task_id)
    task_manager._max_tasks = 1
    with pytest.raises(ValidationError):
        await task_manager.run_task(collect, username=42)
    assert task_id in task_manager.tasks
    await task_manager.shutdown()


async def test_admitted_task_remains_tracked_until_shutdown(task_manager):
    manager = task_manager
    admission = asyncio.create_task(manager.run_task(lambda: 1, "owner"))
    task_id = await admission
    assert task_id in manager.futures
    await manager.shutdown()
    assert (await manager.get_task(task_id)).status == "completed"


async def test_cancelled_thread_remains_tracked_until_worker_exits(task_manager):
    import threading

    started = asyncio.Event()
    released, finished, cancelled = (
        threading.Event(),
        threading.Event(),
        asyncio.Event(),
    )
    loop = asyncio.get_running_loop()

    def worker(cancellation_event):
        loop.call_soon_threadsafe(started.set)
        if not cancellation_event.wait(5):
            raise TimeoutError("Worker did not receive cancellation")
        loop.call_soon_threadsafe(cancelled.set)
        if not released.wait(5):
            raise TimeoutError("Worker was not released")
        finished.set()

    manager = task_manager
    task_id = await manager.run_task(worker)
    shutdown = None
    try:
        async with asyncio.timeout(5):
            await started.wait()
            await manager.cancel_task(task_id)
            await cancelled.wait()
            shutdown = asyncio.create_task(manager.shutdown())
            assert not shutdown.done()
            assert (await manager.get_task(task_id)).status == "cancelling"
            released.set()
            await shutdown
        assert finished.is_set()
        assert (await manager.get_task(task_id)).status == "cancelled"
    finally:
        released.set()
        if shutdown is not None:
            await shutdown


async def test_task_http_and_socket_snapshots_share_transition_revisions(task_manager):
    started = asyncio.Event()
    finish = asyncio.Event()

    async def target():
        started.set()
        await finish.wait()
        return "done"

    task_id = await task_manager.run_task(target, "admin")
    queued = await task_manager.get_task(task_id)
    await started.wait()
    running = await task_manager.get_task(task_id)
    assert running.epoch == queued.epoch
    assert running.revision > queued.revision
    assert (await task_manager.get_all_tasks())[task_id] == running
    # Reading or sending again must not invent a newer task revision.
    assert task_manager._snapshot(task_id) == running
    finish.set()
    completed = await finish_task(task_manager, task_id)
    assert completed.epoch == running.epoch
    assert completed.revision > running.revision


async def test_task_socket_and_http_use_identical_revisions(
    task_manager, subscribed_socket, test_admin_user
):
    finish = asyncio.Event()

    async def target():
        await finish.wait()
        return "done"

    async with subscribed_socket() as socket:
        task_id = await task_manager.run_task(target, test_admin_user.username)
        try:
            async with asyncio.timeout(5):
                message = json.loads(await socket.recv())
            snapshot = await task_manager.get_task(task_id)
            assert message["data"] == snapshot.model_dump(mode="json")
            assert snapshot.revision > 0
            assert snapshot.epoch
            finish.set()
            completed = await finish_task(task_manager, task_id)
            async with asyncio.timeout(5):
                message = json.loads(await socket.recv())
            assert message["data"] == completed.model_dump(mode="json")
            assert completed.revision > snapshot.revision
        finally:
            finish.set()


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
    with pytest.raises(OperationConflictError):
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


async def test_explicit_concurrency_limit_keeps_waiting_tasks_queued():
    manager = TaskManager(None, max_workers=1)
    entered, release = asyncio.Event(), asyncio.Event()
    calls = []

    async def operation(name):
        calls.append(name)
        entered.set()
        await release.wait()

    first = await manager.run_task(operation, None, "first")
    await entered.wait()
    second = await manager.run_task(operation, None, "second")
    await asyncio.sleep(0)
    assert (await manager.get_task(first)).status == "running"
    assert (await manager.get_task(second)).status == "queued"
    assert calls == ["first"]
    assert manager.diagnostic_snapshot().concurrency_limit == 1
    await manager.cancel_task(second)
    release.set()
    await manager.shutdown()
    assert calls == ["first"]
    assert (await manager.get_task(second)).status == "cancelled"


@pytest.mark.parametrize(
    "status,result,error",
    [
        ("completed", None, "failed"),
        ("failed", None, None),
        ("running", 42, None),
    ],
)
def test_task_contract_rejects_contradictory_states(status, result, error):
    from pydantic import ValidationError

    from bedrock_server_manager.api.models.tasks import TaskSnapshot
    from bedrock_server_manager.contracts import FailureInfo

    err_obj = (
        FailureInfo(code="internal_error", message="Failed")
        if error == "failed"
        else None
    )
    with pytest.raises(ValidationError):
        TaskSnapshot(
            id="task", status=status, message="State", result=result, error=err_obj
        )
