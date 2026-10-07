"""Explicit error mapping at serialized boundaries, with no raw input values."""

from pydantic import ValidationError

from ..error import (
    APICancelledError,
    BSMError,
    InvalidServerNameError,
    ServerError,
    ServerStartError,
    ServerStopError,
)
from .models import APIErrorResponse


def error_response(error: Exception) -> APIErrorResponse:
    """Serialize known failures; unexpected exceptions remain private in logs."""
    if isinstance(error, ValidationError):
        return APIErrorResponse(
            code="validation_error",
            message="API data failed validation.",
            details={
                "errors": [
                    {"location": list(item["loc"]), "code": item["type"]}
                    for item in error.errors(include_input=False, include_context=False)
                ]
            },
        )
    if isinstance(error, APICancelledError):
        return APIErrorResponse(
            code="operation_canceled", message="Operation canceled by a plugin."
        )
    if isinstance(error, InvalidServerNameError):
        return APIErrorResponse(
            code="invalid_server_name", message="Invalid server name."
        )
    if isinstance(error, ServerStartError):
        return APIErrorResponse(
            code="server_start_failed", message="The server could not be started."
        )
    if isinstance(error, ServerStopError):
        return APIErrorResponse(
            code="server_stop_failed", message="The server could not be stopped."
        )
    if isinstance(error, ServerError):
        return APIErrorResponse(
            code="server_error", message="The server operation failed."
        )
    if isinstance(error, BSMError):
        return APIErrorResponse(
            code="application_error", message="The application operation failed."
        )
    return APIErrorResponse(
        code="internal_error", message="An unexpected error occurred."
    )
