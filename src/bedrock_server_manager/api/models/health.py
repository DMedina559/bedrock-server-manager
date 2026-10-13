"""Typed application readiness checks, independent of Bedrock server status."""

from typing import Literal

from pydantic import Field

from ...services.lifecycle import LifecyclePhase
from .common import APIRequest, SuccessResponse


class GetApplicationHealthRequest(APIRequest):
    pass


class HealthCheck(SuccessResponse):
    healthy: bool
    message: str


class GetApplicationHealthResponse(SuccessResponse):
    ready: bool
    lifecycle: LifecyclePhase = Field(strict=False)
    health: Literal["healthy", "degraded"]
    checks: dict[str, HealthCheck]
    checked_at: float = Field(gt=0)
