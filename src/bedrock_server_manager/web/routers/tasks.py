# bedrock_server_manager/web/routers/tasks.py
from fastapi import APIRouter, Depends, HTTPException, Security

from ...api.models.tasks import TaskSnapshot
from ...context import AppContext
from ..access_metadata import describe_access
from ..access_policy import Permission
from ..authorization import current_authorization
from ..deps import get_app_context
from ..deps.auth import require_permissions
from ..schemas import UserResponse

router = APIRouter(tags=["Background Tasks"])


@router.get(
    "/api/tasks/status/{task_id}",
    operation_id="get_task_status",
    response_model=TaskSnapshot,
)
@describe_access(
    "permission", authentication="required", additional_checks=["task-owner"]
)
async def get_task_status(
    task_id: str,
    current_user: UserResponse = Security(
        require_permissions, scopes=[Permission.TASKS_READ]
    ),
    app_context: AppContext = Depends(get_app_context),
) -> TaskSnapshot:
    """Return the status of a background task."""
    task = await app_context.task_manager.get_task(
        task_id, username=current_user.username
    )
    authorization = current_authorization.get()
    if (
        task
        and authorization is not None
        and not await app_context.access_service.task_allowed(authorization, task_id)
    ):
        task = None
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get(
    "/api/tasks/list",
    operation_id="list_tasks",
    response_model=list[TaskSnapshot],
)
@describe_access(
    "permission", authentication="required", additional_checks=["task-owner"]
)
async def list_tasks(
    current_user: UserResponse = Security(
        require_permissions, scopes=[Permission.TASKS_READ]
    ),
    app_context: AppContext = Depends(get_app_context),
) -> list[TaskSnapshot]:
    """Return all background tasks."""
    tasks = await app_context.task_manager.get_all_tasks(username=current_user.username)
    authorization = current_authorization.get()
    if authorization is None:
        return list(tasks.values())
    return [
        task
        for identifier, task in tasks.items()
        if await app_context.access_service.task_allowed(authorization, identifier)
    ]
