"""Administrator scheduler configuration and status endpoints."""

from fastapi import APIRouter, Depends, Response, Security

from ...api import scheduler as api
from ...api.models.common import SuccessResponse
from ...api.models.scheduler import (
    ControlSchedulePayload,
    ControlScheduleRequest,
    DeleteScheduleRequest,
    ListSchedulesRequest,
    ListSchedulesResponse,
    SaveScheduleRequest,
)
from ...context import AppContext
from ...state.settings import ScheduledTask
from ..access_policy import Permission
from ..deps import get_app_context
from ..deps.auth import require_permissions

router = APIRouter(
    prefix="/api/scheduler",
    tags=["Scheduler"],
    dependencies=[Security(require_permissions, scopes=[Permission.SCHEDULER_MANAGE])],
)


@router.get(
    "/schedules", operation_id="list_schedules", response_model=ListSchedulesResponse
)
async def list_schedules(
    response: Response,
    server_name: str | None = None,
    context: AppContext = Depends(get_app_context),
) -> ListSchedulesResponse:
    response.headers["Cache-Control"] = "no-store"
    return await api.list_schedules(
        ListSchedulesRequest(server_name=server_name), app_context=context
    )


@router.put(
    "/schedules/{schedule_id}",
    operation_id="save_schedule",
    response_model=SuccessResponse,
)
async def save_schedule(
    schedule_id: str,
    configuration: ScheduledTask,
    context: AppContext = Depends(get_app_context),
) -> SuccessResponse:
    return await api.save_schedule(
        SaveScheduleRequest(schedule_id=schedule_id, configuration=configuration),
        app_context=context,
    )


@router.delete(
    "/schedules/{schedule_id}",
    operation_id="delete_schedule",
    response_model=SuccessResponse,
)
async def delete_schedule(
    schedule_id: str, context: AppContext = Depends(get_app_context)
) -> SuccessResponse:
    return await api.delete_schedule(
        DeleteScheduleRequest(schedule_id=schedule_id), app_context=context
    )


@router.post(
    "/schedules/{schedule_id}/action",
    operation_id="control_schedule",
    response_model=SuccessResponse,
)
async def control_schedule(
    schedule_id: str,
    payload: ControlSchedulePayload,
    context: AppContext = Depends(get_app_context),
) -> SuccessResponse:
    return await api.control_schedule(
        ControlScheduleRequest(schedule_id=schedule_id, **payload.model_dump()),
        app_context=context,
    )
