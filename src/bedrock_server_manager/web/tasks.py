# bedrock_server_manager/web/tasks.py
import uuid
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

tasks: Dict[str, Dict[str, Any]] = {}


def create_task() -> str:
    """Creates a new task and returns the task ID."""
    task_id = str(uuid.uuid4())
    tasks[task_id] = {"status": "pending", "message": "Task created."}
    return task_id


def update_task(
    task_id: str, status: str, message: str, result: Optional[Dict[str, Any]] = None
):
    """Updates the status of a task."""
    tasks[task_id] = {"status": status, "message": message, "result": result}


def get_task(task_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves the status of a task."""
    return tasks.get(task_id)


def run_task(task_id: str, target_function, *args, **kwargs):
    """Runs a target function in the background and updates the task status."""
    update_task(task_id, "in_progress", "Task is running.")
    try:
        result = target_function(*args, **kwargs)
        update_task(task_id, "success", "Task completed successfully.", result)
    except Exception as e:
        logger.error(f"Task {task_id} failed: {e}", exc_info=True)
        update_task(task_id, "error", str(e))
