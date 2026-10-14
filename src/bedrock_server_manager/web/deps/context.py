import logging

from fastapi import Depends, Request

from ...context import AppContext
from ...events import EventBus

logger = logging.getLogger(__name__)


async def get_app_context(request: Request) -> "AppContext":
    """
    FastAPI dependency to get the application context from the request state.
    """
    return request.app.state.app_context  # type: ignore


def get_event_bus(app_context: AppContext = Depends(get_app_context)) -> EventBus:
    return app_context.events
