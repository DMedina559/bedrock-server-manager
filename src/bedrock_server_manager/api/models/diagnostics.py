"""Diagnostic request and response contracts for application and plugin callers."""

from pydantic import Field

from ...diagnostics.models import (
    DiagnosticHistory,
    DiagnosticReport,
    DiagnosticSnapshot,
)
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


class GetDiagnosticHistoryResponse(DiagnosticHistory, APIResponse):
    pass


class GetDiagnosticReportRequest(APIRequest):
    pass


class GetDiagnosticReportResponse(DiagnosticReport, APIResponse):
    pass
