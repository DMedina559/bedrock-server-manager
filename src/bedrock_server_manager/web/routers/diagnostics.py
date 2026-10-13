"""Administrator-only metadata snapshots and sanitized support history."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from ...context import AppContext
from ...diagnostics.models import (
    DiagnosticHistory,
    DiagnosticReport,
    DiagnosticSnapshot,
)
from ...diagnostics.service import Diagnostics
from ..deps import get_admin_user
from ..deps.context import get_app_context

router = APIRouter(
    prefix="/api/diagnostics",
    tags=["Diagnostics"],
    dependencies=[Depends(get_admin_user)],
)


def get_diagnostics(context: AppContext = Depends(get_app_context)) -> Diagnostics:
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
    "/history", operation_id="get_diagnostic_history", response_model=DiagnosticHistory
)
async def get_diagnostic_history(
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    subsystem: Annotated[str | None, Query(max_length=80)] = None,
    instance_id: Annotated[str | None, Query(max_length=32)] = None,
    correlation_id: Annotated[str | None, Query(max_length=160)] = None,
    service: Diagnostics = Depends(get_diagnostics),
) -> DiagnosticHistory:
    return await service.history.read(
        limit=limit,
        subsystem=subsystem,
        instance_id=instance_id,
        correlation_id=correlation_id,
    )


@router.get(
    "/report", operation_id="get_diagnostic_report", response_model=DiagnosticReport
)
async def get_diagnostic_report(
    service: Diagnostics = Depends(get_diagnostics),
) -> DiagnosticReport:
    """Export typed sanitized metadata with bounded history across application runs."""
    return DiagnosticReport(
        snapshot=await service.snapshot(), history=await service.history.read()
    )


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
