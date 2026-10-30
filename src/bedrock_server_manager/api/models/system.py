"""Serializable system, health, and metrics API request and response contracts."""

from typing import Literal

from pydantic import Field

from ...services.lifecycle import LifecyclePhase
from ...services.metrics_models import MetricsSample as MetricsSample
from ...services.metrics_models import MetricsSnapshot
from ...services.metrics_models import ServerMetrics as ServerMetrics
from .common import APIRequest, APIResponse, ServerName, StateRevision, SuccessResponse


class ProcessInfo(APIResponse):
    pid: int
    cpu_percent: float
    memory_mb: float
    uptime: str


class GetServerRunningStatusRequest(APIRequest):
    server_name: ServerName


class GetServerRunningStatusResponse(SuccessResponse, StateRevision):
    is_running: bool


class GetBedrockProcessInfoRequest(APIRequest):
    server_name: ServerName


class GetBedrockProcessInfoResponse(SuccessResponse, StateRevision):
    process_info: ProcessInfo | None


class GetApplicationHealthRequest(APIRequest):
    pass


class HealthCheck(SuccessResponse):
    healthy: bool
    message: str


class GetApplicationHealthResponse(SuccessResponse):
    pid: int = Field(gt=0)
    instance_id: str | None = None
    version: str
    ready: bool
    lifecycle: LifecyclePhase = Field(strict=False)
    health: Literal["healthy", "degraded"]
    checks: dict[str, HealthCheck]
    checked_at: float = Field(gt=0)


class GetApplicationMetricsRequest(APIRequest):
    pass


class GetApplicationMetricsResponse(MetricsSnapshot, APIResponse):
    pass


__all__ = [
    "ProcessInfo",
    "GetServerRunningStatusRequest",
    "GetServerRunningStatusResponse",
    "GetBedrockProcessInfoRequest",
    "GetBedrockProcessInfoResponse",
    "GetApplicationHealthRequest",
    "HealthCheck",
    "GetApplicationHealthResponse",
    "MetricsSample",
    "ServerMetrics",
    "GetApplicationMetricsRequest",
    "GetApplicationMetricsResponse",
]
