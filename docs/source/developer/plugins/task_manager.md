# Background tasks

Await server start, stop, and restart directly. Use a background task when a
long operation, such as a backup or download, should continue after an HTTP
request returns. Async functions run on the event loop; synchronous functions
run in a worker thread. Use asynchronous I/O or move blocking work to a thread.

## Submitting a task

Use `self.api.runtime.run_task`. It returns a task ID. Supply the authenticated
user's username so polling and WebSocket updates belong to that user.

```python
import asyncio
from fastapi import APIRouter, Depends
from bedrock_server_manager import PluginBase
from bedrock_server_manager.api.models.tasks import TaskAcceptedResponse
from bedrock_server_manager.web import get_admin_user
from bedrock_server_manager.web.schemas import UserResponse

class MyTaskPlugin(PluginBase):
    version = "4.0.0"

    async def collect(self):
        await asyncio.sleep(5)
        return {"message": "Collection finished."}

    def get_fastapi_routers(self):
        router = APIRouter(prefix="/my_task_plugin", tags=["My Task Plugin"])

        @router.post("/collect", operation_id="my_task_plugin_collect",
                     response_model=TaskAcceptedResponse)
        async def collect(current_user: UserResponse = Depends(get_admin_user)):
            task_id = await self.api.runtime.run_task(
                self.collect, username=current_user.username
            )
            return TaskAcceptedResponse(task_id=task_id, message="Collection queued.")

        return [router]
```

Return JSON data or a serializable Pydantic model from your function. Errors are
logged and exposed as a safe structured error, without raw exception details.

## Tracking a task

Task status is `queued`, `running`, `completed`, `failed`, `cancelling`, or `cancelled`.
Polling and WebSocket updates use the same task snapshot:

```json
{
    "id": "task-id",
    "status": "completed",
    "message": "Task completed.",
    "result": {"message": "Collection finished."},
    "error": null
}
```

Updates are sent to the owner on `task:{task_id}`. A completed API operation can
still have `status="skipped"` in its result; inspect the operation result as well
as the task status. A cancellation request sets `cancelling` until execution
finishes. Synchronous functions cannot be forcibly stopped; the manager waits
for their worker before reporting `cancelled` or completing shutdown.

For cooperative cancellation, declare a `cancellation_event` parameter. The
manager supplies a `threading.Event` and sets it when cancellation is requested:

```python
from threading import Event

def collect(cancellation_event: Event):
    while not cancellation_event.wait(1):
        # Perform one bounded unit of work.
        pass
```

Use timeouts for blocking I/O so your function can check the event regularly.

## Using `@task_loop` for Periodic Tasks

If you need a task to run continuously in the background on a fixed interval (e.g., polling an external API, performing cleanups), you don't need to manually interact with the `TaskManager`.

Instead, use the `@task_loop(interval)` decorator provided by the plugin system. The `PluginManager` will automatically schedule these methods as background tasks when your plugin is loaded and cancel them when it is unloaded.

Both synchronous and asynchronous methods are supported.

```python
import asyncio
import time
from bedrock_server_manager import PluginBase
from bedrock_server_manager.plugins.task_loop import task_loop

class MyPollingPlugin(PluginBase):
    version = "1.0.0"

    # Async example
    @task_loop(interval=300) # Runs every 5 minutes (300 seconds)
    async def poll_remote_service_async(self):
        self.logger.info("Polling remote service asynchronously...")
        # Simulate an I/O bound request safely without blocking the event loop
        await asyncio.sleep(2)
        self.logger.info("Async polling complete.")

    # Sync example
    @task_loop(interval=60) # Runs every 1 minute
    def clean_up_local_files_sync(self):
        self.logger.info("Cleaning up files synchronously...")
        # The Plugin Manager automatically runs this in a thread pool
        # so time.sleep won't freeze the main app loop.
        time.sleep(1)
        self.logger.info("Sync cleanup complete.")
```
