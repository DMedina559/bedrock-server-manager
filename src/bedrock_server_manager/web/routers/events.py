"""Administrative event catalog and metadata-only runtime diagnostics."""

from fastapi import APIRouter, Depends

from ...context import AppContext
from ...events.models import EventCatalog, EventDiagnostics
from ..deps import get_admin_user, get_app_context

router = APIRouter(tags=["Application Events"], dependencies=[Depends(get_admin_user)])


@router.get(
    "/api/events", operation_id="list_application_events", response_model=EventCatalog
)
async def list_application_events(
    app_context: AppContext = Depends(get_app_context),
) -> EventCatalog:
    return app_context.events.registry.catalog()


@router.get(
    "/api/events/activity",
    operation_id="get_event_activity",
    response_model=EventDiagnostics,
)
async def get_event_activity(
    app_context: AppContext = Depends(get_app_context),
) -> EventDiagnostics:
    return app_context.events.diagnostics()
