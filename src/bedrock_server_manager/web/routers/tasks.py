# bedrock_server_manager/web/routers/tasks.py
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any

from ..auth_utils import get_current_user
from .. import tasks

router = APIRouter()


@router.get("/api/tasks/status/{task_id}", tags=["Tasks"])
async def get_task_status(
    task_id: str, current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Retrieves the status of a background task.
    """
    task = tasks.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task
