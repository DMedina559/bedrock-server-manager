"""Administrative event catalog and metadata-only runtime diagnostics."""

from fastapi import APIRouter, Depends

from ...events import EventBus
from ...events.models import EventActivityQuery, EventCatalog, EventDiagnostics
from ..deps import get_admin_user
from ..deps.context import get_event_bus

router = APIRouter(tags=["Application Events"], dependencies=[Depends(get_admin_user)])


@router.get(
    "/api/events", operation_id="list_application_events", response_model=EventCatalog
)
async def list_application_events(
    events: EventBus = Depends(get_event_bus),
) -> EventCatalog:
    return events.registry.catalog()


@router.get(
    "/api/events/activity",
    operation_id="get_event_activity",
    response_model=EventDiagnostics,
)
async def get_event_activity(
    query: EventActivityQuery = Depends(),
    events: EventBus = Depends(get_event_bus),
) -> EventDiagnostics:
    return events.diagnostics(query)
