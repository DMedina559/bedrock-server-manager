"""Diagnostic request and response contracts for application and plugin callers."""

from typing import Literal

from pydantic import Field

from ...diagnostics.models import (
    DiagnosticActivity,
    DiagnosticComparison,
    DiagnosticHistory,
    DiagnosticReport,
    DiagnosticRuns,
    DiagnosticSnapshot,
    DiagnosticTrace,
)
from ...events.models import EventActivityQuery
from .common import APIRequest, APIResponse


class GetApplicationDiagnosticsRequest(APIRequest):
    subsystem: str | None = Field(default=None, max_length=80)


class GetApplicationDiagnosticsResponse(DiagnosticSnapshot, APIResponse):
    pass


class GetDiagnosticHistoryRequest(APIRequest):
    limit: int = Field(default=100, ge=1, le=200)
    subsystem: str | None = Field(default=None, max_length=80)
    instance_id: str | None = Field(default=None, max_length=32)
    correlation_id: str | None = Field(default=None, max_length=160)
    cursor: str | None = Field(default=None, max_length=512)
    owner: str | None = Field(default=None, max_length=160)
    code: str | None = Field(default=None, max_length=80)
    outcome: Literal["completed", "failed", "cancelled"] | None = None
    operation_id: str | None = Field(default=None, max_length=160)


class GetDiagnosticHistoryResponse(DiagnosticHistory, APIResponse):
    pass


class GetDiagnosticReportRequest(APIRequest):
    pass


class GetDiagnosticReportResponse(DiagnosticReport, APIResponse):
    pass


class GetDiagnosticRunsRequest(APIRequest):
    limit: int = Field(default=20, ge=1, le=50)


class GetDiagnosticRunsResponse(DiagnosticRuns, APIResponse):
    pass


class GetDiagnosticTraceRequest(APIRequest):
    correlation_id: str = Field(min_length=1, max_length=160)
    limit: int = Field(default=100, ge=1, le=200)
    cursor: str | None = Field(default=None, max_length=512)


class GetDiagnosticTraceResponse(DiagnosticTrace, APIResponse):
    pass


class CompareDiagnosticSnapshotsRequest(APIRequest):
    before: DiagnosticSnapshot
    after: DiagnosticSnapshot


class CompareDiagnosticSnapshotsResponse(DiagnosticComparison, APIResponse):
    pass


class GetDiagnosticActivityRequest(EventActivityQuery, APIRequest):
    limit: int = Field(default=100, ge=1, le=200)


class GetDiagnosticActivityResponse(DiagnosticActivity, APIResponse):
    pass
