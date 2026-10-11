"""Typed application readiness checks, independent of Bedrock server status."""

from typing import Literal

from pydantic import Field

from .common import APIRequest, SuccessResponse


class GetApplicationHealthRequest(APIRequest):
    pass


class HealthCheck(SuccessResponse):
    healthy: bool
    message: str


class GetApplicationHealthResponse(SuccessResponse):
    health: Literal["healthy", "degraded"]
    checks: dict[str, HealthCheck]
    checked_at: float = Field(gt=0)
