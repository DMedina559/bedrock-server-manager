"""Expose typed diagnostic data without granting provider registration capabilities."""

from ..context import AppContext
from ..error import ResourceNotFoundError
from ..plugins.api_bridge import api_method
from .models.diagnostics import (
    GetApplicationDiagnosticsRequest,
    GetApplicationDiagnosticsResponse,
    GetDiagnosticHistoryRequest,
    GetDiagnosticHistoryResponse,
    GetDiagnosticReportRequest,
    GetDiagnosticReportResponse,
)


@api_method("get_application_diagnostics")
async def get_application_diagnostics(
    request: GetApplicationDiagnosticsRequest, *, app_context: AppContext
) -> GetApplicationDiagnosticsResponse:
    """Read bounded subsystem metadata; unavailable providers remain isolated."""
    result = await app_context.diagnostics.snapshot(request.subsystem)
    if request.subsystem is not None and not result.sections:
        raise ResourceNotFoundError("Unknown diagnostic subsystem")
    return GetApplicationDiagnosticsResponse.model_validate(result.model_dump())


@api_method("get_diagnostic_history")
async def get_diagnostic_history(
    request: GetDiagnosticHistoryRequest, *, app_context: AppContext
) -> GetDiagnosticHistoryResponse:
    """Read sanitized retained records, optionally scoped to an application run."""
    result = await app_context.diagnostics.history.read(**request.model_dump())
    return GetDiagnosticHistoryResponse.model_validate(result.model_dump())


@api_method("get_diagnostic_report")
async def get_diagnostic_report(
    request: GetDiagnosticReportRequest, *, app_context: AppContext
) -> GetDiagnosticReportResponse:
    """Build a support report without secrets, task arguments, or event payloads."""
    return GetDiagnosticReportResponse(
        snapshot=await app_context.diagnostics.snapshot(),
        history=await app_context.diagnostics.history.read(),
    )
