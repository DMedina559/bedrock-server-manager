# Using the Task Manager

When developing plugins for Bedrock Server Manager, you may encounter situations where a task takes a long time to complete (e.g., downloading large files, processing backups, making complex external API calls).

Running these tasks directly within an event hook or a FastAPI endpoint blocks the main application thread or event loop. This can cause the web interface to become unresponsive and potentially lead to WebSocket disconnections.

To solve this, Bedrock Server Manager provides a `TaskManager` to offload long-running operations to background threads.

## Submitting Background Tasks via `self.api.run_task`

In Version 4.0, plugins interact with background task scheduling exclusively through the safe `self.api.run_task` method. Plugins **must not** attempt to access `app_context` or `TaskManager` objects directly.

The `await self.api.run_task(...)` method accepts the target function to execute along with any required positional or keyword arguments, submitting the function to be executed in the background and returning a unique `task_id`.

### Example: A Long-Running Task

Here is an example of a plugin that provides a web endpoint to trigger a long-running background task.

```python
import time
import logging
from fastapi import APIRouter, Depends
from bedrock_server_manager import PluginBase

# It is recommended to import the application context dependency
# to cleanly access the task manager from decoupled FastAPI routers.
from bedrock_server_manager.web.dependencies import get_app_context
from bedrock_server_manager.web.auth_utils import get_current_user
from bedrock_server_manager.context import AppContext
from bedrock_server_manager.web.schemas import User

logger = logging.getLogger(__name__)

plugin_web_router = APIRouter(
    prefix="/my_task_plugin",
    tags=["My Task Plugin"]
)

def my_long_running_function(seconds: int, name: str):
    """This function runs in the background."""
    logger.info(f"Starting long task for {name}...")
    # Simulate a long-running process
    time.sleep(seconds)
    logger.info(f"Finished long task for {name}!")
    return f"Processed {name} successfully in {seconds} seconds."

class MyTaskPlugin(PluginBase):
    version = "4.0.0"

    @app_event("on_load")
    async def plugin_loaded(self, **kwargs):
        self.logger.info("MyTaskPlugin loaded.")

    def get_fastapi_routers(self):
        router = APIRouter(prefix="/my_task_plugin", tags=["My Task Plugin"])

        @router.post("/start_task")
        async def trigger_task(
            seconds: int = 5,
            name: str = "example",
            current_user: Dict[str, Any] = Depends(get_admin_user)
        ):
            # Submit the function to run in the background via self.api.run_task.
            task_id = await self.api.run_task(
                my_long_running_function,
                username=current_user.get("username"),
                seconds=seconds,
                name=name
            )

            return {"status": "success", "task_id": task_id, "message": "Task started in the background."}

        return [router]
```

## Tracking Task Status and UI Updates

When you submit a task using `run_task`, the `TaskManager` automatically tracks its status (`in_progress`, `success`, `error`).

The task manager returns a dictionary containing the task details:

```json
{
    "status": "in_progress", // Or "success", "error"
    "message": "Task is running.", // Or the error/success message
    "result": null, // Will contain the return value of your function upon success
    "username": "admin"
}
```

### WebSocket Notifications

If you provide the `username` argument when calling `run_task`, the `TaskManager` will automatically send WebSocket notifications to that specific user whenever the task status updates (e.g., when it completes or fails).

The frontend can listen for these notifications on the `task:{task_id}` topic to update the UI without needing to poll the `task_status` endpoint repeatedly.

### Handling Exceptions

If your background function raises an exception, the task manager will catch it, log the error using the main application logger, and update the task's status to `error`. The exception message will be stored in the task's `message` field.



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
