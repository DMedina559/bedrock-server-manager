# bedrock_server_manager/web/tasks.py
import asyncio
import inspect
import logging
import uuid
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional

if TYPE_CHECKING:
    from ..context import AppContext

logger = logging.getLogger(__name__)


class TaskManager:
    """Manages background tasks using asyncio."""

    def __init__(self, app_context: "AppContext", max_workers: Optional[int] = None):
        """Initializes the TaskManager."""
        self.app_context = app_context
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self.futures: Dict[str, asyncio.Task] = {}
        self._shutdown_started = False
        self._max_tasks = 100
        self._background_tasks: set[asyncio.Task] = set()

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

            try:
                loop = self.app_context.loop
            except RuntimeError:
                logger.debug(
                    f"Skipping task update notification for task {task_id}: No running event loop available."
                )
                return

            if loop is not None and loop.is_running():
                task = asyncio.create_task(
                    connection_manager.send_to_user(username, message)
                )
                self._background_tasks.add(task)
                task.add_done_callback(self._background_tasks.discard)

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

    def _task_done_callback(self, task_id: str, future: asyncio.Task):
        """Callback function executed when a task completes."""
        try:
            if future.cancelled():
                self._update_task(task_id, "error", "Task was cancelled.")
                return
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
        Supports both asynchronous functions (scheduled directly)
        and synchronous functions (run in an executor via asyncio.to_thread).

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

        # Enforce max tasks limit to prevent memory leaks
        if len(self.tasks) >= self._max_tasks:
            # Remove the oldest task (first item inserted)
            oldest_task_id = next(iter(self.tasks))
            del self.tasks[oldest_task_id]
            if oldest_task_id in self.futures:
                del self.futures[oldest_task_id]

        self.tasks[task_id] = {
            "status": "in_progress",
            "message": "Task is running.",
            "result": None,
            "username": username,
        }
        self._notify_client_of_update(task_id)

        try:
            loop = self.app_context.loop
        except RuntimeError:
            loop = None

        if loop is None or not loop.is_running():
            # No running loop, so we have to run it synchronously (e.g. during some tests or early startup)
            logger.warning(
                f"Task {task_id}: No running event loop. Running target function synchronously."
            )
            try:
                if inspect.iscoroutinefunction(target_function):
                    result = asyncio.run(target_function(*args, **kwargs))
                else:
                    result = target_function(*args, **kwargs)
                self._update_task(
                    task_id, "success", "Task completed successfully.", result
                )
            except Exception as e:
                self._update_task(task_id, "error", str(e))
            return task_id

        if inspect.iscoroutinefunction(target_function):
            coro = target_function(*args, **kwargs)
        else:
            # Standard synchronous function, run it in a thread
            def sync_wrapper():
                return target_function(*args, **kwargs)

            coro = asyncio.to_thread(sync_wrapper)

        task = asyncio.create_task(coro)
        self.futures[task_id] = task
        task.add_done_callback(lambda f: self._task_done_callback(task_id, f))

        return task_id

    def cancel_task(self, task_id: str) -> bool:
        """
        Attempts to cancel a running task.

        Args:
            task_id (str): The ID of the task to cancel.

        Returns:
            bool: True if the task was found and cancellation was requested, False otherwise.
        """
        if task_id not in self.futures:
            return False

        task = self.futures[task_id]
        task.cancel()

        self._update_task(task_id, "error", "Task was cancelled.")
        return True

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves the status of a task."""
        return self.tasks.get(task_id)

    def get_all_tasks(self) -> Dict[str, Dict[str, Any]]:
        """Retrieves all tasks."""
        return self.tasks

    async def shutdown(self):
        """Waits for all background tasks to complete asynchronously."""
        self._shutdown_started = True
        logger.info(
            "Task manager shutting down. Waiting for running tasks to complete."
        )

        tasks = list(self.futures.values())
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        logger.info("All tasks have completed. Task manager shutdown finished.")
