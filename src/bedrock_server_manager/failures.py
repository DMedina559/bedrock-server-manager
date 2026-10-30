"""One failure classification for Python transports and diagnostic logging."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from pydantic import ValidationError

from .contracts import ClassifiedFailure, FailureInfo

if TYPE_CHECKING:
    from .api.models.common import APIErrorResponse
from .error import (
    APICancelledError,
    AppFileNotFoundError,
    BlockedCommandError,
    BSMError,
    ConfigurationError,
    DependencyUnavailableError,
    FileError,
    IncompleteOperationError,
    InvalidServerNameError,
    NetworkError,
    OperationConflictError,
    ResourceNotFoundError,
    ServerError,
    ServerNotRunningError,
    ServerRunningError,
    ServerStartError,
    ServerStopError,
    StorageError,
    SystemError,
    UserInputError,
)


def classify_failure(error: Exception) -> ClassifiedFailure:
    fastapi_exc = sys.modules.get("fastapi.exceptions")
    request_validation_error = getattr(fastapi_exc, "RequestValidationError", ())
    starlette_exc = sys.modules.get("starlette.exceptions")
    http_exception = getattr(starlette_exc, "HTTPException", ())
    if isinstance(error, (ValidationError, request_validation_error)):
        items = error.errors()
        return ClassifiedFailure(
            status_code=422,
            expected=True,
            error=FailureInfo(
                code="validation_error",
                message="API data failed validation.",
                details={
                    "errors": [
                        {"location": list(item["loc"]), "code": item["type"]}
                        for item in items
                    ]
                },
            ),
        )
    if isinstance(error, http_exception):
        code = {
            400: "validation_error",
            401: "unauthorized",
            403: "forbidden",
            404: "not_found",
            409: "conflict",
            422: "validation_error",
            503: "unavailable",
        }.get(error.status_code, "http_error")
        if error.status_code >= 500 and error.status_code != 503:
            code = "internal_error"
        return ClassifiedFailure(
            status_code=error.status_code,
            expected=error.status_code < 500,
            error=FailureInfo.model_validate(
                {
                    "code": code,
                    "message": (
                        error.detail
                        if isinstance(error.detail, str) and error.status_code < 500
                        else (
                            "A required service is unavailable."
                            if error.status_code == 503
                            else "An unexpected error occurred."
                        )
                    ),
                }
            ),
        )
    mappings = (
        (BlockedCommandError, "forbidden", 403, "Command is blocked."),
        (ServerNotRunningError, "conflict", 409, "Server is not running."),
        (ServerRunningError, "conflict", 409, "Server is still running."),
        (
            OperationConflictError,
            "conflict",
            409,
            "The operation conflicts with the current state.",
        ),
        (
            APICancelledError,
            "operation_canceled",
            409,
            "Operation canceled before execution.",
        ),
        (InvalidServerNameError, "invalid_server_name", 400, "Invalid server name."),
        (AppFileNotFoundError, "not_found", 404, "Resource not found."),
        (ResourceNotFoundError, "not_found", 404, "Resource not found."),
        (
            DependencyUnavailableError,
            "unavailable",
            503,
            "A required service is unavailable.",
        ),
        (
            IncompleteOperationError,
            "operation_incomplete",
            500,
            "The operation did not complete.",
        ),
        (UserInputError, "validation_error", 400, str(error)),
        (
            ServerStartError,
            "server_start_failed",
            500,
            "The server could not be started.",
        ),
        (
            ServerStopError,
            "server_stop_failed",
            500,
            "The server could not be stopped.",
        ),
        (ServerError, "server_error", 500, "The server operation failed."),
        (StorageError, "storage_error", 500, "The storage operation failed."),
        (FileError, "file_error", 500, "The filesystem operation failed."),
        (
            ConfigurationError,
            "configuration_error",
            500,
            "Configuration could not be read or applied.",
        ),
        (
            NetworkError,
            "network_error",
            503,
            "A required network service is unavailable.",
        ),
        (SystemError, "system_error", 500, "The system operation failed."),
        (OSError, "file_error", 500, "The filesystem operation failed."),
        (BSMError, "application_error", 500, "The application operation failed."),
    )
    for kind, code, status, message in mappings:
        if isinstance(error, kind):
            details = (
                {"result": error.result.model_dump(mode="json")}
                if isinstance(error, IncompleteOperationError)
                else {}
            )
            return ClassifiedFailure(
                status_code=status,
                expected=status < 500 and not isinstance(error, AppFileNotFoundError),
                error=FailureInfo.model_validate(
                    {"code": code, "message": message, "details": details}
                ),
            )
    return ClassifiedFailure(
        status_code=500,
        expected=False,
        error=FailureInfo(
            code="internal_error", message="An unexpected error occurred."
        ),
    )


def error_status_code(error: Exception) -> int:
    return classify_failure(error).status_code


def error_response(error: Exception) -> APIErrorResponse:
    from .api.models.common import APIErrorResponse

    return APIErrorResponse.model_validate(classify_failure(error).error.model_dump())
