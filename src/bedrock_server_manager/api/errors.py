"""Serialized API failures reuse the application-wide classifier."""

from ..failures import classify_failure
from .models import APIErrorResponse


def error_status_code(error: Exception) -> int:
    return classify_failure(error).status_code


def error_response(error: Exception) -> APIErrorResponse:
    return APIErrorResponse.model_validate(classify_failure(error).error.model_dump())
