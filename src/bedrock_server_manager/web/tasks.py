# bedrock_server_manager/web/tasks.py
import asyncio
import inspect
import logging
import math
import time
import uuid
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional

if TYPE_CHECKING:
    from ..diagnostics.service import Diagnostics

from pydantic import BaseModel, ValidationError

from ..api.models.tasks import TaskSnapshot
from ..diagnostics.models import TaskDiagnostic, TasksDiagnostics
from ..error import APICancelledError, OperationConflictError, UserInputError
from ..events.bus import correlation_scope, current_correlation_id
from ..logging import log_operation_error
from ..plugins.api_contract import APIResponseValidationError
from ..state_revision import revision_clock
from ..utils.threads import run_in_thread
from .task_record import TaskRecord
from .websocket_manager import ConnectionManager

logger = logging.getLogger(__name__)
_current_task_id: ContextVar[str | None] = ContextVar("managed_task_id", default=None)


class TaskManager:
    """Manage background tasks using asyncio."""

    def __init__(
        self,
        connection_manager: ConnectionManager | None,
        max_workers: Optional[int] = None,
        *,
        diagnostics: "Diagnostics | None" = None,
    ):
        """Initialize the TaskManager with explicit dependencies."""
        self.diagnostics = diagnostics
        self._metadata: dict[str, dict[str, Any]] = {}
        self._timing: dict[str, tuple[float, float | None]] = {}
        self.connection_manager = connection_manager
        self._tasks: Dict[str, TaskRecord] = {}
        self.futures: Dict[str, asyncio.Task] = {}
        self._shutdown_started = False
        self._max_tasks = 100
        self._background_tasks: set[asyncio.Task] = set()
        self._plugin_owners: dict[str, str] = {}
        self._blocked_plugins: set[str] = set()

    @property
    def active_task_count(self) -> int:
        """Count unfinished managed operations, including plugin-owned tasks."""
        return sum(not task.done() for task in self.futures.values())

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
                    "Skipping task update notification for task %s: No running event loop available.",
                    task_id,
                )
                return

            if loop is not None and loop.is_running():
                try:
                    await asyncio.wait_for(
                        connection_manager.send_to_user(username, message), timeout=5
                    )
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
            data.update(
                status=status,
                message=message,
                result=None,
                error=None,
                **revision_clock.capture(),
            )
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
            if (
                status == "completed"
                and self._metadata.get(task_id, {}).get("progress_percent") is not None
            ):
                self._metadata[task_id]["progress_percent"] = 100.0
            if (
                status in {"completed", "failed", "cancelled"}
                and task_id in self._timing
            ):
                started, finished = self._timing[task_id]
                if finished is None:
                    self._timing[task_id] = started, time.monotonic()
                    if self.diagnostics is not None:
                        self.diagnostics.record_task(
                            task_id,
                            record,
                            started=started,
                            owner=self._plugin_owners.get(task_id),
                            name=self._metadata.get(task_id, {}).get(
                                "name", "background_task"
                            ),
                            correlation_id=self._metadata.get(task_id, {}).get(
                                "correlation_id"
                            ),
                        )
            notification = asyncio.create_task(self._notify_client_of_update(task_id))
            self._background_tasks.add(notification)
            notification.add_done_callback(self._background_tasks.discard)

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
                log_operation_error(logger, "Task %s failed: %s", task_id, e, error=e)
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
        _plugin_owner: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Submit owned sync or async work and return its task ID."""
        if self._shutdown_started:
            raise RuntimeError(
                "Cannot start new tasks after shutdown has been initiated."
            )

        if _plugin_owner in self._blocked_plugins:
            raise RuntimeError("Cannot submit work for an unloading plugin.")

        candidate = TaskRecord(
            status="queued",
            message="Task is queued.",
            username=username,
            **revision_clock.capture(),
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
                from ..error import OperationConflictError

                raise OperationConflictError("Background task capacity reached.")
            del self._tasks[oldest_task_id]
            self._plugin_owners.pop(oldest_task_id, None)
            self._timing.pop(oldest_task_id, None)
            self._metadata.pop(oldest_task_id, None)
            if oldest_task_id in self.futures:
                del self.futures[oldest_task_id]

        self._tasks[task_id] = candidate
        self._timing[task_id] = time.monotonic(), None
        actual = getattr(target_function, "func", target_function)
        self._metadata[task_id] = {
            "name": getattr(actual, "__name__", type(actual).__name__)[:160],
            "correlation_id": current_correlation_id() or uuid.uuid4().hex,
            "progress_percent": None,
            "cancellation_requested": False,
        }
        if _plugin_owner is not None:
            self._plugin_owners[task_id] = _plugin_owner

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

        async def _runner():
            token = _current_task_id.set(task_id)
            try:
                with correlation_scope(self._metadata[task_id]["correlation_id"]):
                    await self._update_task(task_id, "running", "Task is running.")
                    if inspect.iscoroutinefunction(target_function):
                        return await target_function(*args, **call_kwargs)
                    return await run_in_thread(target_function, *args, **call_kwargs)
            finally:
                _current_task_id.reset(token)

        task = asyncio.create_task(_runner())
        self.futures[task_id] = task
        task.add_done_callback(lambda f: self._task_done_callback(task_id, f))

        return task_id

    def report_progress(
        self, percent: float, *, plugin_owner: str | None = None
    ) -> None:
        """Update only the current running task; progress is unknown until reported."""
        task_id = _current_task_id.get()
        if task_id is None or task_id not in self._tasks:
            raise OperationConflictError("Progress requires a running managed task")
        if self._plugin_owners.get(task_id) != plugin_owner:
            raise UserInputError("Task progress belongs to another owner")
        if self._tasks[task_id].status != "running":
            raise OperationConflictError("Task is no longer running")
        if (
            isinstance(percent, bool)
            or not isinstance(percent, (int, float))
            or not math.isfinite(percent)
            or not 0 <= percent <= 100
        ):
            raise UserInputError(
                "Progress must be a finite percentage between 0 and 100"
            )
        self._metadata[task_id]["progress_percent"] = float(percent)

    def diagnostic_snapshot(self) -> TasksDiagnostics:
        """Read bounded task identity and timing without arguments or result payloads."""
        from collections import Counter

        items = []
        for task_id, record in self._tasks.items():
            started, ended = self._timing.get(task_id, (None, None))
            metadata = self._metadata.get(task_id, {})
            future = self.futures.get(task_id)
            items.append(
                TaskDiagnostic(
                    id=task_id,
                    status=record.status,
                    owner=self._plugin_owners.get(task_id),
                    name=metadata.get("name", "background_task"),
                    correlation_id=metadata.get("correlation_id"),
                    cancellation_requested=metadata.get("cancellation_requested", False)
                    or bool(future and future.cancelling()),
                    progress_percent=metadata.get("progress_percent"),
                    error_code=record.error.code if record.error else None,
                    elapsed_seconds=(
                        max(0, (ended or time.monotonic()) - started)
                        if started is not None
                        else None
                    ),
                )
            )
        active_ages = [
            item.elapsed_seconds
            for item in items
            if item.status in {"queued", "running", "cancelling"}
            and item.elapsed_seconds is not None
        ]
        return TasksDiagnostics(
            active=self.active_task_count,
            tasks=items,
            accepting=not self._shutdown_started,
            counts_by_status=dict(
                Counter(record.status for record in self._tasks.values())
            ),
            capacity=self._max_tasks,
            oldest_active_seconds=max(active_ages) if active_ages else None,
        )

    async def cancel_task(self, task_id: str) -> bool:
        """Attempts to cancel a running task.

        :param task_id: The ID of the task to cancel.

        :returns: True if the task was found and cancellation was requested, False otherwise.
        """
        if task_id not in self.futures:
            return False

        task = self.futures[task_id]
        if task.done():
            return False
        self._metadata.get(task_id, {})["cancellation_requested"] = True
        if not task.done() and not task.cancelling():
            task.cancel()

        await self._update_task(
            task_id,
            "cancelling",
            "Cancellation requested; waiting for execution to finish.",
        )
        return True

    def _snapshot(self, task_id: str) -> TaskSnapshot:
        record = self._tasks[task_id]
        result = record["result"]
        if isinstance(result, BaseModel):
            result = result.model_dump(mode="json")
        return TaskSnapshot.model_validate(
            {
                "id": task_id,
                "epoch": record.epoch,
                "revision": record.revision,
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

    def allow_plugin(self, plugin_name: str) -> None:
        self._blocked_plugins.discard(plugin_name)

    async def drain_plugin(self, plugin_name: str) -> None:
        owned = [
            (task_id, future)
            for task_id, future in self.futures.items()
            if self._plugin_owners.get(task_id) == plugin_name
        ]
        tasks = [future for _, future in owned]
        if asyncio.current_task() in tasks:
            raise RuntimeError("An owned task cannot unload its own plugin.")
        self._blocked_plugins.add(plugin_name)
        for task_id, task in owned:
            self._metadata.get(task_id, {})["cancellation_requested"] = True
            if not task.done() and not task.cancelling():
                task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        await asyncio.sleep(0)

    def begin_shutdown(self) -> None:
        """Close admission before producers and running operations are drained."""
        self._shutdown_started = True

    async def shutdown(self):
        """Waits for all background tasks to complete asynchronously."""
        self.begin_shutdown()
        logger.debug(
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

        logger.debug("All tasks have completed. Task manager shutdown finished.")
