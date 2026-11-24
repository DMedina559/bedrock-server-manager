"""Administrator-only metadata snapshots and sanitized support history."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, Security
from pydantic import Field

from ...context import AppContext
from ...diagnostics.comparison import compare_snapshots
from ...diagnostics.service import Diagnostics
from ...models.diagnostics import (
    CompareDiagnosticSnapshotsRequest,
    CompareDiagnosticSnapshotsResponse,
    GetApplicationDiagnosticsResponse,
    GetDiagnosticActivityRequest,
    GetDiagnosticActivityResponse,
    GetDiagnosticHistoryResponse,
    GetDiagnosticReportResponse,
    GetDiagnosticRunsResponse,
    GetDiagnosticTraceResponse,
)
from ..access_policy import Permission
from ..deps.auth import require_permissions
from ..deps.context import get_app_context

router = APIRouter(
    prefix="/api/diagnostics",
    tags=["Diagnostics"],
    dependencies=[Security(require_permissions, scopes=[Permission.DIAGNOSTICS_READ])],
)


def get_diagnostics(
    response: Response, context: AppContext = Depends(get_app_context)
) -> Diagnostics:
    response.headers["Cache-Control"] = "no-store"
    return context.diagnostics


@router.get(
    "",
    operation_id="get_application_diagnostics",
    response_model=GetApplicationDiagnosticsResponse,
)
async def get_application_diagnostics(
    service: Diagnostics = Depends(get_diagnostics),
) -> GetApplicationDiagnosticsResponse:
    """Collect bounded metadata without probing server processes or database health."""
    result = await service.snapshot()
    return GetApplicationDiagnosticsResponse.model_validate(result.model_dump())


class DiagnosticActivityQuery(GetDiagnosticActivityRequest):
    """Parse URL integers without relaxing the strict plugin API contract."""

    limit: int = Field(default=100, ge=1, le=200, strict=False)


@router.get(
    "/activity",
    operation_id="get_diagnostic_activity",
    response_model=GetDiagnosticActivityResponse,
)
async def get_diagnostic_activity(
    query: Annotated[DiagnosticActivityQuery, Query()],
    service: Diagnostics = Depends(get_diagnostics),
) -> GetDiagnosticActivityResponse:
    """Read global activity, optionally narrowing by event, server, sequence, or correlation."""
    return GetDiagnosticActivityResponse.model_validate(
        service.activity(query).model_dump()
    )


@router.get(
    "/history",
    operation_id="get_diagnostic_history",
    response_model=GetDiagnosticHistoryResponse,
)
async def get_diagnostic_history(
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    subsystem: Annotated[str | None, Query(max_length=80)] = None,
    instance_id: Annotated[str | None, Query(max_length=32)] = None,
    correlation_id: Annotated[str | None, Query(max_length=160)] = None,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    owner: Annotated[str | None, Query(max_length=160)] = None,
    code: Annotated[str | None, Query(max_length=80)] = None,
    outcome: Literal["completed", "failed", "cancelled"] | None = None,
    operation_id: Annotated[str | None, Query(max_length=160)] = None,
    service: Diagnostics = Depends(get_diagnostics),
) -> GetDiagnosticHistoryResponse:
    result = await service.history.read(
        limit=limit,
        subsystem=subsystem,
        instance_id=instance_id,
        correlation_id=correlation_id,
        cursor=cursor,
        owner=owner,
        code=code,
        outcome=outcome,
        operation_id=operation_id,
    )
    return GetDiagnosticHistoryResponse.model_validate(result.model_dump())


@router.get(
    "/report",
    operation_id="get_diagnostic_report",
    response_model=GetDiagnosticReportResponse,
)
async def get_diagnostic_report(
    response: Response,
    service: Diagnostics = Depends(get_diagnostics),
) -> GetDiagnosticReportResponse:
    """Export typed sanitized metadata with bounded history across application runs."""
    report = await service.report()
    response.headers["Content-Disposition"] = (
        f'attachment; filename="bsm-diagnostics-{report.report_id}.json"'
    )
    return GetDiagnosticReportResponse.model_validate(report.model_dump())


@router.get(
    "/runs",
    operation_id="get_diagnostic_runs",
    response_model=GetDiagnosticRunsResponse,
)
async def get_diagnostic_runs(
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    service: Diagnostics = Depends(get_diagnostics),
) -> GetDiagnosticRunsResponse:
    result = await service.history.runs(
        current_instance=service.instance_id, limit=limit
    )
    return GetDiagnosticRunsResponse.model_validate(result.model_dump())


@router.get(
    "/trace/{correlation_id}",
    operation_id="get_diagnostic_trace",
    response_model=GetDiagnosticTraceResponse,
)
async def get_diagnostic_trace(
    correlation_id: str,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    service: Diagnostics = Depends(get_diagnostics),
) -> GetDiagnosticTraceResponse:
    result = await service.trace(correlation_id, limit=limit, cursor=cursor)
    return GetDiagnosticTraceResponse.model_validate(result.model_dump())


@router.post(
    "/compare",
    operation_id="compare_diagnostic_snapshots",
    response_model=CompareDiagnosticSnapshotsResponse,
)
async def compare_diagnostic_snapshots(
    request: CompareDiagnosticSnapshotsRequest,
    service: Diagnostics = Depends(get_diagnostics),
) -> CompareDiagnosticSnapshotsResponse:
    """Compare supplied metadata; administrator authentication is required."""
    return CompareDiagnosticSnapshotsResponse.model_validate(
        compare_snapshots(request.before, request.after).model_dump()
    )


@router.get(
    "/{subsystem}",
    operation_id="get_subsystem_diagnostics",
    response_model=GetApplicationDiagnosticsResponse,
)
async def get_subsystem_diagnostics(
    subsystem: str, service: Diagnostics = Depends(get_diagnostics)
) -> GetApplicationDiagnosticsResponse:
    result = await service.snapshot(subsystem)
    if not result.sections:
        raise HTTPException(status_code=404, detail="Unknown diagnostic subsystem")
    return GetApplicationDiagnosticsResponse.model_validate(result.model_dump())
