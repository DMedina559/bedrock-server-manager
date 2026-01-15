# bedrock_server_manager/web/routers/tasks.py
from fastapi import APIRouter, Depends, HTTPException

from ...context import AppContext
from ..auth_utils import get_current_user
from ..dependencies import get_app_context
from ..schemas import User

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
