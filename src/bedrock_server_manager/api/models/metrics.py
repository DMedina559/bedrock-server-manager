"""Application performance observations; unavailable measurements remain null."""

from pydantic import Field

from .common import APIRequest, APIResponse, StateRevision, SuccessResponse


class GetApplicationMetricsRequest(APIRequest):
    pass


class ServerMetrics(APIResponse):
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


class GetApplicationMetricsResponse(SuccessResponse, StateRevision):
    latest: MetricsSample
    history: list[MetricsSample]
    interval_seconds: float = Field(gt=0)
    history_limit: int = Field(gt=0, le=180)
