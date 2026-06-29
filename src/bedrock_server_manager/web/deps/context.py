import logging

from fastapi import Request

from ...context import AppContext

logger = logging.getLogger(__name__)


def get_app_context(request: Request) -> "AppContext":
    """
    FastAPI dependency to get the application context from the request state.
    """
    return request.app.state.app_context  # type: ignore
