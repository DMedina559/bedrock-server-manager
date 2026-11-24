"""Serializable system, health, and metrics API request and response contracts."""

from typing import Literal

from pydantic import Field

from .common import (
    APIRequest,
    APIResponse,
    DataContract,
    LifecyclePhase,
    NonEmptyStr,
    ServerName,
    StateRevision,
    SuccessResponse,
)


class FileNamePayload(APIRequest):
    """Payload for file-based operations.

    :ivar filename: The name of the file to operate on.
    """

    filename: NonEmptyStr


class ServerMetrics(DataContract):
    server_name: str
    pid: int | None = Field(default=None, gt=0)
    cpu_percent: float | None = Field(default=None, ge=0)
    memory_mb: float | None = Field(default=None, ge=0)


class MetricsSample(StateRevision):
    timestamp: float = Field(gt=0)
    app_cpu_percent: float | None = Field(default=None, ge=0)
    app_ram_mb: float | None = Field(default=None, ge=0)
    thread_count: int | None = Field(default=None, ge=0)
    asyncio_task_count: int = Field(ge=0)
    background_task_count: int = Field(ge=0)
    loop_lag_ms: float = Field(ge=0)
    uptime_seconds: float | None = Field(default=None, ge=0)
    sys_cpu_percent: float | None = Field(default=None, ge=0)
    sys_ram_mb: float | None = Field(default=None, ge=0)
    sys_ram_total_mb: float | None = Field(default=None, ge=0)
    sys_ram_percent: float | None = Field(default=None, ge=0)
    net_tx_kib_s: float | None = Field(default=None, ge=0)
    net_rx_kib_s: float | None = Field(default=None, ge=0)
    disk_read_kib_s: float | None = Field(default=None, ge=0)
    disk_write_kib_s: float | None = Field(default=None, ge=0)
    servers: list[ServerMetrics] = Field(default_factory=list)


class MetricsSnapshot(StateRevision):
    status: Literal["success"] = "success"
    message: str | None = None
    latest: MetricsSample
    history: list[MetricsSample]
    interval_seconds: float = Field(gt=0)
    history_limit: int = Field(gt=0, le=180)


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
    health: Literal["healthy", "degraded", "unhealthy"]
    checks: dict[str, HealthCheck]
    checked_at: float = Field(gt=0)


class GetApplicationMetricsRequest(APIRequest):
    pass


class GetApplicationMetricsResponse(MetricsSnapshot, APIResponse):
    pass


__all__ = [
    "FileNamePayload",
    "ProcessInfo",
    "GetServerRunningStatusRequest",
    "GetServerRunningStatusResponse",
    "GetBedrockProcessInfoRequest",
    "GetBedrockProcessInfoResponse",
    "GetApplicationHealthRequest",
    "HealthCheck",
    "GetApplicationHealthResponse",
    "MetricsSample",
    "MetricsSnapshot",
    "ServerMetrics",
    "GetApplicationMetricsRequest",
    "GetApplicationMetricsResponse",
]
