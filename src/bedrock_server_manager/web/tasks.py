# bedrock_server_manager/web/tasks.py
import asyncio
import inspect
import logging
import uuid
from typing import Any, Callable, Dict, Optional

from pydantic import BaseModel, ValidationError

from ..api.models.tasks import TaskSnapshot
from ..error import APICancelledError
from ..plugins.api_contract import APIResponseValidationError
from .task_record import TaskRecord

logger = logging.getLogger(__name__)


class TaskManager:
    """Manages background tasks using asyncio."""

    def __init__(
        self,
        connection_manager: Any,
        max_workers: Optional[int] = None,
    ):
        """Initializes the TaskManager with explicit dependencies."""
        self.connection_manager = connection_manager
        self._tasks: Dict[str, TaskRecord] = {}
        self.futures: Dict[str, asyncio.Task] = {}
        self._shutdown_started = False
        self._max_tasks = 100
        self._background_tasks: set[asyncio.Task] = set()

    @property
    def tasks(self) -> Dict[str, TaskRecord]:
        """Independent snapshots; execution records remain owned by this manager."""
        return {
            name: record.model_copy(deep=True) for name, record in self._tasks.items()
        }

    async def _notify_client_of_update(self, task_id: str):
        """Sends a WebSocket notification to the user associated with the task."""
        task_details = self._tasks.get(task_id)
        if not task_details:
            return

        username = task_details.get("username")
        if username and self.connection_manager:
            connection_manager = self.connection_manager
            message = {
                "type": "task_update",
                "topic": f"task:{task_id}",
                "data": self._snapshot(task_id).model_dump(mode="json"),
            }

            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                logger.debug(
                    f"Skipping task update notification for task {task_id}: No running event loop available."
                )
                return

            if loop is not None and loop.is_running():
                try:
                    await connection_manager.send_to_user(username, message)
                except Exception:
                    logger.warning(
                        "Could not deliver task update %s", task_id, exc_info=True
                    )

    async def _update_task(
        self,
        task_id: str,
        status: str,
        message: str,
        result: Optional[Any] = None,
        error: Optional[Any] = None,
    ):
        """Helper function to update the status of a task and notify client."""
        if task_id in self._tasks:
            data = dict(self._tasks[task_id])
            data.update(status=status, message=message)
            if result is not None:
                data["result"] = (
                    result.model_dump(mode="json")
                    if isinstance(result, BaseModel)
                    else result
                )
            if error is not None:
                data.update(result=None, error=error)
            try:
                record = TaskRecord.model_validate(data)
            except ValidationError as validation_error:
                raise APIResponseValidationError(
                    "Background task returned invalid JSON data."
                ) from validation_error
            self._tasks[task_id] = record
            await self._notify_client_of_update(task_id)

    def _task_done_callback(self, task_id: str, future: asyncio.Task):
        """Callback function executed when a task completes."""

        async def handle_done():
            try:
                if future.cancelled():
                    await self._update_task(task_id, "cancelled", "Task was cancelled.")
                    return
                result = future.result()
                await self._update_task(task_id, "completed", "Task completed.", result)
            except Exception as e:
                logger.error(f"Task {task_id} failed: {e}", exc_info=True)
                from ..api.errors import error_response

                error = error_response(e)
                await self._update_task(
                    task_id,
                    "cancelled" if isinstance(e, APICancelledError) else "failed",
                    error.message,
                    error=error,
                )
            finally:
                # Clean up the future from the tracking dictionary
                if task_id in self.futures:
                    del self.futures[task_id]

        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                # We are in an event loop, create a task to run the async update
                update_task = loop.create_task(handle_done())
                self._background_tasks.add(update_task)
                update_task.add_done_callback(self._background_tasks.discard)
            else:
                asyncio.run(handle_done())
        except RuntimeError:
            # No event loop
            asyncio.run(handle_done())

    async def run_task(
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

        candidate = TaskRecord(
            status="queued", message="Task is queued.", username=username
        )
        task_id = str(uuid.uuid4())

        # Enforce max tasks limit to prevent memory leaks
        if len(self._tasks) >= self._max_tasks:
            # Remove the oldest task (first item inserted)
            oldest_task_id = next(
                (
                    key
                    for key in self._tasks
                    if key not in self.futures
                    and self._tasks[key]["status"]
                    in {"completed", "failed", "cancelled"}
                ),
                None,
            )
            if oldest_task_id is None:
                raise RuntimeError("Background task capacity reached.")
            del self._tasks[oldest_task_id]
            if oldest_task_id in self.futures:
                del self.futures[oldest_task_id]

        self._tasks[task_id] = candidate
        await self._notify_client_of_update(task_id)

        call_kwargs = dict(kwargs)
        if username is not None:
            try:
                sig = inspect.signature(target_function)
                has_var_kw = any(
                    p.kind == inspect.Parameter.VAR_KEYWORD
                    for p in sig.parameters.values()
                )
                if "username" in sig.parameters or has_var_kw:
                    call_kwargs["username"] = username
            except (ValueError, TypeError):
                pass

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is None or not loop.is_running():
            # No running loop, so we have to run it synchronously (e.g. during some tests or early startup)
            logger.warning(
                f"Task {task_id}: No running event loop. Running target function synchronously."
            )
            try:
                if inspect.iscoroutinefunction(target_function):
                    result = asyncio.run(target_function(*args, **call_kwargs))
                else:
                    result = target_function(*args, **call_kwargs)
                await self._update_task(task_id, "completed", "Task completed.", result)
            except Exception as e:
                logger.error(f"Task {task_id} failed: {e}", exc_info=True)
                from ..api.errors import error_response

                error = error_response(e)
                await self._update_task(
                    task_id,
                    "cancelled" if isinstance(e, APICancelledError) else "failed",
                    error.message,
                    error=error,
                )
            return task_id

        async def _runner():
            await self._update_task(task_id, "running", "Task is running.")
            if inspect.iscoroutinefunction(target_function):
                return await target_function(*args, **call_kwargs)
            else:

                def sync_wrapper():
                    return target_function(*args, **call_kwargs)

                return await asyncio.to_thread(sync_wrapper)

        task = asyncio.create_task(_runner())
        self.futures[task_id] = task
        task.add_done_callback(lambda f: self._task_done_callback(task_id, f))

        return task_id

    async def cancel_task(self, task_id: str) -> bool:
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

        await self._update_task(task_id, "cancelled", "Task was cancelled.")
        return True

    def _snapshot(self, task_id: str) -> TaskSnapshot:
        record = self._tasks[task_id]
        result = record["result"]
        if isinstance(result, BaseModel):
            result = result.model_dump(mode="json")
        return TaskSnapshot.model_validate(
            {
                "id": task_id,
                "status": record["status"],
                "message": record["message"],
                "result": result,
                "error": record["error"],
            }
        )

    async def get_task(
        self, task_id: str, *, username: str | None = None
    ) -> TaskSnapshot | None:
        record = self._tasks.get(task_id)
        if record is None or (username is not None and record["username"] != username):
            return None
        return self._snapshot(task_id)

    async def get_all_tasks(
        self, *, username: str | None = None
    ) -> dict[str, TaskSnapshot]:
        return {
            key: self._snapshot(key)
            for key, record in self._tasks.items()
            if username is None or record["username"] == username
        }

    async def shutdown(self):
        """Waits for all background tasks to complete asynchronously."""
        self._shutdown_started = True
        logger.info(
            "Task manager shutting down. Waiting for running tasks to complete."
        )

        tasks = list(self.futures.values())
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        await asyncio.sleep(0)
        while self._background_tasks:
            updates = list(self._background_tasks)
            await asyncio.gather(*updates, return_exceptions=True)
            self._background_tasks.difference_update(updates)

        logger.info("All tasks have completed. Task manager shutdown finished.")
