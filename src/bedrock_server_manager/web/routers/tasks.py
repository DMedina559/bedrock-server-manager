# bedrock_server_manager/web/routers/tasks.py
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any

from ..auth_utils import get_current_user
from ..schemas import User
from .. import tasks

router = APIRouter()


@router.get("/api/tasks/status/{task_id}", tags=["Tasks"])
async def get_task_status(task_id: str, current_user: User = Depends(get_current_user)):
    """
    Retrieves the status of a background task.

    Args:
        task_id (str): The ID of the task to retrieve.
        current_user (User, optional): The current authenticated user. Defaults to Depends(get_current_user).

    Raises:
        HTTPException: If the task is not found.

    Returns:
        Dict[str, Any]: The status of the task.
    """
    task = tasks.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task
