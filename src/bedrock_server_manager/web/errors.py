"""Register consistent, sanitized HTTP exception responses."""

import logging

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from ..api.models.common import APIErrorResponse, ErrorEnvelope
from ..error import BSMError
from ..failures import classify_failure
from ..logging import log_operation_error
from ..plugins.api_contract import APIResponseValidationError

logger = logging.getLogger(__name__)


def configure_errors(app: FastAPI) -> None:
    """Install exception handlers without changing transport status or headers."""

    async def api_error_handler(request, error):
        headers = None
        classified = classify_failure(error)
        status_code = classified.status_code
        payload = APIErrorResponse.model_validate(classified.error.model_dump())
        headers = getattr(error, "headers", None)
        if not classified.expected:
            log_operation_error(
                logger,
                "HTTP operation failed: %s %s",
                request.method,
                request.url.path,
                error=error,
            )
        return JSONResponse(
            status_code=status_code,
            headers=headers,
            content=ErrorEnvelope(error=payload).model_dump(mode="json"),
        )

    for exception_type in (
        ValidationError,
        BSMError,
        APIResponseValidationError,
        RequestValidationError,
        ResponseValidationError,
        StarletteHTTPException,
        Exception,
    ):
        app.add_exception_handler(exception_type, api_error_handler)
