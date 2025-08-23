# bedrock_server_manager/web/routers/tasks.py
from fastapi import APIRouter, Depends, HTTPException, Request
from typing import Dict, Any

from ..auth_utils import get_current_user
from ..schemas import User
from ..dependencies import get_app_context
from ...context import AppContext

router = APIRouter()


@router.get("/api/tasks/status/{task_id}", tags=["Tasks"])
async def get_task_status(
    task_id: str,
    current_user: User = Depends(get_current_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Retrieves the status of a background task.
    """
    task = app_context.task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task
