"""HTTP and plugin contracts for shared performance observations."""

from ...services.metrics_models import MetricsSample as MetricsSample
from ...services.metrics_models import MetricsSnapshot
from ...services.metrics_models import ServerMetrics as ServerMetrics
from .common import APIRequest, APIResponse


class GetApplicationMetricsRequest(APIRequest):
    pass


class GetApplicationMetricsResponse(MetricsSnapshot, APIResponse):
    pass


__all__ = [
    "MetricsSample",
    "ServerMetrics",
    "GetApplicationMetricsRequest",
    "GetApplicationMetricsResponse",
]
