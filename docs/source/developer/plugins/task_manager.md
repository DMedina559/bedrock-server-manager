# Using the Task Manager

When developing plugins for Bedrock Server Manager, you may encounter situations where a task takes a long time to complete (e.g., downloading large files, processing backups, making complex external API calls).

Running these tasks directly within an event hook or a FastAPI endpoint blocks the main application thread or event loop. This can cause the web interface to become unresponsive and potentially lead to WebSocket disconnections.

To solve this, Bedrock Server Manager provides a `TaskManager` to offload long-running operations to background threads.

## Accessing the Task Manager

You can access the `TaskManager` instance via your plugin's `api` object. The task manager is attached to the main application context:

```python
task_manager = self.api.app_context.task_manager()
```

## Running Background Tasks

The primary method you will use is `run_task`. This method submits a function to be executed in the background and immediately returns a unique `task_id`.

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

@plugin_web_router.post("/start_task")
async def start_task(
    seconds: int = 5,
    name: str = "example",
    app_context: AppContext = Depends(get_app_context),
    current_user: User = Depends(get_current_user)
):
    """Starts a task using the injected AppContext and User."""
    task_manager = app_context.task_manager()

    task_id = task_manager.run_task(
        my_long_running_function,
        username=current_user.username, # Provide the username for targeted WebSocket UI updates
        seconds=seconds,
        name=name
    )

    return {"status": "success", "task_id": task_id, "message": "Task started in the background."}

class MyTaskPlugin(PluginBase):
    version = "1.0.0"

    def on_load(self):
        self.logger.info("MyTaskPlugin loaded.")

        # We can attach the task manager or API to the router's state if needed
        # Or, we can define the endpoint within the class methods if we want direct `self` access

    def get_fastapi_routers(self):
        # A simpler way to get access to `self.api` is to define the route dynamically here

        router = APIRouter(prefix="/my_task_plugin", tags=["My Task Plugin"])

        @router.post("/start_task")
        async def trigger_task(
            seconds: int = 5,
            name: str = "example",
            current_user: User = Depends(get_current_user)
        ):
            task_manager = self.api.app_context.task_manager()

            # Submit the function to the background.
            # *args and **kwargs passed to run_task will be forwarded to your function.
            task_id = task_manager.run_task(
                my_long_running_function,
                username=current_user.username, # Provide the username for targeted WebSocket UI updates
                seconds=seconds,  # kwarg for my_long_running_function
                name=name         # kwarg for my_long_running_function
            )

            return {"status": "success", "task_id": task_id, "message": "Task started in the background."}

        @router.get("/task_status/{task_id}")
        async def get_task_status(task_id: str):
            task_manager = self.api.app_context.task_manager()
            task_details = task_manager.get_task(task_id)

            if not task_details:
                return {"status": "error", "message": "Task not found."}

            return {"status": "success", "task": task_details}

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
