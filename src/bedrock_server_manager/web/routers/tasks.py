# bedrock_server_manager/web/routers/tasks.py
from fastapi import APIRouter, Depends, HTTPException

from ...api.models.tasks import TaskSnapshot
from ...context import AppContext
from ..deps import get_app_context, get_current_user
from ..schemas import UserResponse

router = APIRouter(tags=["Background Tasks"])


@router.get(
    "/api/tasks/status/{task_id}",
    operation_id="get_task_status",
    response_model=TaskSnapshot,
)
async def get_task_status(
    task_id: str,
    current_user: UserResponse = Depends(get_current_user),
    app_context: AppContext = Depends(get_app_context),
) -> TaskSnapshot:
    """
    Retrieves the status of a background task.
    """
    task = await app_context.task_manager.get_task(
        task_id, username=current_user.username
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get(
    "/api/tasks/list",
    operation_id="list_tasks",
    response_model=list[TaskSnapshot],
)
async def list_tasks(
    current_user: UserResponse = Depends(get_current_user),
    app_context: AppContext = Depends(get_app_context),
) -> list[TaskSnapshot]:
    """
    Retrieves all background tasks.
    """
    tasks = await app_context.task_manager.get_all_tasks(username=current_user.username)
    return list(tasks.values())
