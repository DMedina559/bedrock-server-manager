# bedrock_server_manager/web/tasks.py
import asyncio
import uuid
from typing import Dict, Any, Optional, Callable, TYPE_CHECKING
import logging
from concurrent.futures import ThreadPoolExecutor, Future

if TYPE_CHECKING:
    from ..context import AppContext

logger = logging.getLogger(__name__)


class TaskManager:
    """Manages background tasks using a thread pool."""

    def __init__(self, app_context: "AppContext", max_workers: Optional[int] = None):
        """Initializes the TaskManager and the thread pool executor."""
        self.app_context = app_context
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self.futures: Dict[str, Future] = {}
        self._shutdown_started = False
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)

    def _notify_client_of_update(self, task_id: str):
        """Sends a WebSocket notification to the user associated with the task."""
        task_details = self.tasks.get(task_id)
        if not task_details:
            return

        username = task_details.get("username")
        if username:
            connection_manager = self.app_context.connection_manager
            message = {
                "type": "task_update",
                "topic": f"task:{task_id}",
                "data": task_details,
            }
            # Use run_coroutine_threadsafe because this function is called from a worker thread
            asyncio.run_coroutine_threadsafe(
                connection_manager.send_to_user(username, message), self._loop
            )

    def _update_task(
        self, task_id: str, status: str, message: str, result: Optional[Any] = None
    ):
        """Helper function to update the status of a task and notify client."""
        if task_id in self.tasks:
            self.tasks[task_id]["status"] = status
            self.tasks[task_id]["message"] = message
            if result is not None:
                self.tasks[task_id]["result"] = result
            self._notify_client_of_update(task_id)

    def _task_done_callback(self, task_id: str, future: Future):
        """Callback function executed when a task completes."""
        try:
            result = future.result()
            self._update_task(
                task_id, "success", "Task completed successfully.", result
            )
        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}", exc_info=True)
            self._update_task(task_id, "error", str(e))
        finally:
            # Clean up the future from the tracking dictionary
            if task_id in self.futures:
                del self.futures[task_id]

    def run_task(
        self,
        target_function: Callable,
        username: Optional[str] = None,
        *args: Any,
        **kwargs: Any,
    ) -> str:
        """
        Submits a function to be run in the background.

        Args:
            target_function: The function to execute.
            username: The user associated with the task for WebSocket notifications.
            *args: Positional arguments for the target function.
            **kwargs: Keyword arguments for the target function.

        Returns:
            The ID of the created task.
        """
        if self._shutdown_started:
            raise RuntimeError(
                "Cannot start new tasks after shutdown has been initiated."
            )

        task_id = str(uuid.uuid4())
        self.tasks[task_id] = {
            "status": "in_progress",
            "message": "Task is running.",
            "result": None,
            "username": username,
        }
        self._notify_client_of_update(task_id)

        future = self.executor.submit(target_function, *args, **kwargs)
        self.futures[task_id] = future
        future.add_done_callback(lambda f: self._task_done_callback(task_id, f))

        return task_id

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves the status of a task."""
        return self.tasks.get(task_id)

    def shutdown(self):
        """Shuts down the thread pool and waits for all tasks to complete."""
        self._shutdown_started = True
        logger.info(
            "Task manager shutting down. Waiting for running tasks to complete."
        )
        self.executor.shutdown(wait=True)
        logger.info("All tasks have completed. Task manager shutdown finished.")
