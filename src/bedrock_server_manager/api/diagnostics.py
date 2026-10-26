"""Expose typed diagnostic data without granting provider registration capabilities."""

from ..context import AppContext
from ..diagnostics.comparison import compare_snapshots
from ..error import ResourceNotFoundError
from ..plugins.api_bridge import api_method
from .models.diagnostics import (
    CompareDiagnosticSnapshotsRequest,
    CompareDiagnosticSnapshotsResponse,
    GetApplicationDiagnosticsRequest,
    GetApplicationDiagnosticsResponse,
    GetDiagnosticActivityRequest,
    GetDiagnosticActivityResponse,
    GetDiagnosticHistoryRequest,
    GetDiagnosticHistoryResponse,
    GetDiagnosticReportRequest,
    GetDiagnosticReportResponse,
    GetDiagnosticRunsRequest,
    GetDiagnosticRunsResponse,
    GetDiagnosticTraceRequest,
    GetDiagnosticTraceResponse,
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
    report = await app_context.diagnostics.report()
    return GetDiagnosticReportResponse.model_validate(report.model_dump())


@api_method("get_diagnostic_runs")
async def get_diagnostic_runs(
    request: GetDiagnosticRunsRequest, *, app_context: AppContext
) -> GetDiagnosticRunsResponse:
    """List retained application instances without guessing whether older runs are alive."""
    runs = await app_context.diagnostics.history.runs(
        current_instance=app_context.diagnostics.instance_id, limit=request.limit
    )
    return GetDiagnosticRunsResponse.model_validate(runs.model_dump())


@api_method("get_diagnostic_trace")
async def get_diagnostic_trace(
    request: GetDiagnosticTraceRequest, *, app_context: AppContext
) -> GetDiagnosticTraceResponse:
    """Read events, tasks, and retained failures sharing one correlation identity."""
    trace = await app_context.diagnostics.trace(**request.model_dump())
    return GetDiagnosticTraceResponse.model_validate(trace.model_dump())


@api_method("compare_diagnostic_snapshots")
async def compare_diagnostic_snapshots(
    request: CompareDiagnosticSnapshotsRequest, *, app_context: AppContext
) -> CompareDiagnosticSnapshotsResponse:
    """Compare metadata snapshots without treating restarted counters as activity."""
    comparison = compare_snapshots(request.before, request.after)
    return CompareDiagnosticSnapshotsResponse.model_validate(comparison.model_dump())


@api_method("get_diagnostic_activity")
async def get_diagnostic_activity(
    request: GetDiagnosticActivityRequest, *, app_context: AppContext
) -> GetDiagnosticActivityResponse:
    """Read all-chain event, operation, and subscription metadata without payloads."""
    return GetDiagnosticActivityResponse.model_validate(
        app_context.diagnostics.activity(request).model_dump()
    )
