"""Administrator-managed schedules and plugin-readable task metadata."""

from ..context import AppContext
from ..plugins.api_bridge import api_method
from .models.common import SuccessResponse
from .models.scheduler import (
    ControlScheduleRequest,
    DeleteScheduleRequest,
    ListSchedulesRequest,
    ListSchedulesResponse,
    SaveScheduleRequest,
)


@api_method("list_schedules")
async def list_schedules(
    request: ListSchedulesRequest, *, app_context: AppContext
) -> ListSchedulesResponse:
    """Read schedule configuration, availability and bounded last-run metadata."""
    return await app_context.scheduler.snapshot(request.server_name)


@api_method("save_schedule", expose_to_plugins=False)
async def save_schedule(
    request: SaveScheduleRequest, *, app_context: AppContext
) -> SuccessResponse:
    """Create or replace a named schedule; newly configured jobs start at their next slot."""
    await app_context.scheduler.save(request)
    return SuccessResponse(message="Schedule saved.")


@api_method("delete_schedule", expose_to_plugins=False)
async def delete_schedule(
    request: DeleteScheduleRequest, *, app_context: AppContext
) -> SuccessResponse:
    """Remove a named schedule without deleting archives or stopping an active run."""
    await app_context.scheduler.delete(request.schedule_id)
    return SuccessResponse(message="Schedule removed.")


@api_method("control_schedule", expose_to_plugins=False)
async def control_schedule(
    request: ControlScheduleRequest, *, app_context: AppContext
) -> SuccessResponse:
    """Queue a manual run/retry or pause/resume a revision-checked schedule."""
    await app_context.scheduler.control(request)
    return SuccessResponse(message="Schedule action accepted.")
