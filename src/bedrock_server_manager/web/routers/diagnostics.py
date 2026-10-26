"""Administrator-only metadata snapshots and sanitized support history."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from ...api.models.diagnostics import (
    CompareDiagnosticSnapshotsRequest,
    GetDiagnosticActivityRequest,
)
from ...context import AppContext
from ...diagnostics.comparison import compare_snapshots
from ...diagnostics.models import (
    DiagnosticActivity,
    DiagnosticComparison,
    DiagnosticHistory,
    DiagnosticReport,
    DiagnosticRuns,
    DiagnosticSnapshot,
    DiagnosticTrace,
)
from ...diagnostics.service import Diagnostics
from ..deps import get_admin_user
from ..deps.context import get_app_context

router = APIRouter(
    prefix="/api/diagnostics",
    tags=["Diagnostics"],
    dependencies=[Depends(get_admin_user)],
)


def get_diagnostics(
    response: Response, context: AppContext = Depends(get_app_context)
) -> Diagnostics:
    response.headers["Cache-Control"] = "no-store"
    return context.diagnostics


@router.get(
    "", operation_id="get_application_diagnostics", response_model=DiagnosticSnapshot
)
async def get_application_diagnostics(
    service: Diagnostics = Depends(get_diagnostics),
) -> DiagnosticSnapshot:
    """Collect bounded metadata without probing server processes or database health."""
    return await service.snapshot()


@router.get(
    "/activity",
    operation_id="get_diagnostic_activity",
    response_model=DiagnosticActivity,
)
async def get_diagnostic_activity(
    query: Annotated[GetDiagnosticActivityRequest, Query()],
    service: Diagnostics = Depends(get_diagnostics),
) -> DiagnosticActivity:
    """Read global activity, optionally narrowing by event, server, sequence, or correlation."""
    return service.activity(query)


@router.get(
    "/history", operation_id="get_diagnostic_history", response_model=DiagnosticHistory
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
) -> DiagnosticHistory:
    return await service.history.read(
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


@router.get(
    "/report", operation_id="get_diagnostic_report", response_model=DiagnosticReport
)
async def get_diagnostic_report(
    response: Response,
    service: Diagnostics = Depends(get_diagnostics),
) -> DiagnosticReport:
    """Export typed sanitized metadata with bounded history across application runs."""
    report = await service.report()
    response.headers["Content-Disposition"] = (
        f'attachment; filename="bsm-diagnostics-{report.report_id}.json"'
    )
    return report


@router.get("/runs", operation_id="get_diagnostic_runs", response_model=DiagnosticRuns)
async def get_diagnostic_runs(
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    service: Diagnostics = Depends(get_diagnostics),
) -> DiagnosticRuns:
    return await service.history.runs(current_instance=service.instance_id, limit=limit)


@router.get(
    "/trace/{correlation_id}",
    operation_id="get_diagnostic_trace",
    response_model=DiagnosticTrace,
)
async def get_diagnostic_trace(
    correlation_id: str,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    service: Diagnostics = Depends(get_diagnostics),
) -> DiagnosticTrace:
    return await service.trace(correlation_id, limit=limit, cursor=cursor)


@router.post(
    "/compare",
    operation_id="compare_diagnostic_snapshots",
    response_model=DiagnosticComparison,
)
async def compare_diagnostic_snapshots(
    request: CompareDiagnosticSnapshotsRequest,
    service: Diagnostics = Depends(get_diagnostics),
) -> DiagnosticComparison:
    """Compare supplied metadata; administrator authentication is required."""
    return compare_snapshots(request.before, request.after)


@router.get(
    "/{subsystem}",
    operation_id="get_subsystem_diagnostics",
    response_model=DiagnosticSnapshot,
)
async def get_subsystem_diagnostics(
    subsystem: str, service: Diagnostics = Depends(get_diagnostics)
) -> DiagnosticSnapshot:
    result = await service.snapshot(subsystem)
    if not result.sections:
        raise HTTPException(status_code=404, detail="Unknown diagnostic subsystem")
    return result
