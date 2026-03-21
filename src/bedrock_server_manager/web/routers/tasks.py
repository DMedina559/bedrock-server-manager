# bedrock_server_manager/web/routers/tasks.py
from fastapi import APIRouter, Depends, HTTPException

from ...context import AppContext
from ..auth_utils import get_current_user
from ..dependencies import get_app_context
from ..schemas import UserResponse

router = APIRouter()


@router.get("/api/tasks/status/{task_id}", tags=["Tasks"])
async def get_task_status(
    task_id: str,
    current_user: UserResponse = Depends(get_current_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Retrieves the status of a background task.
    """
    task = app_context.task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get("/api/tasks/list", tags=["Tasks"])
async def list_tasks(
    current_user: UserResponse = Depends(get_current_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Retrieves all background tasks.
    """
    tasks = app_context.task_manager.get_all_tasks()
    # Convert dict to list of objects with ID
    task_list = []
    for task_id, task_data in tasks.items():
        task_info = task_data.copy()
        task_info["id"] = task_id
        task_list.append(task_info)
    return task_list
