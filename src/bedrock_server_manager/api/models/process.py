"""Process ownership, capabilities and failure evidence for one server."""

from typing import Literal

from pydantic import Field

from .common import APIRequest, APIResponse, ServerName, SuccessResponse


class GetServerProcessRequest(APIRequest):
    server_name: ServerName


class ProcessOutputStatus(APIResponse):
    source: Literal["file", "pipe", "unknown"]
    available: bool
    error: str | None = None
    queued_bytes: int = Field(ge=0)
    dropped_bytes: int = Field(ge=0)


class BanEnforcementStatus(APIResponse):
    available: bool
    error: str | None = None


class ProcessExitStatus(APIResponse):
    code: int | None = None
    reason: str | None = None


class ServerProcessStatus(APIResponse):
    generation: str | None = None
    running: bool
    phase: str | None = None
    ready: bool
    pid: int | None = None
    owned: bool
    recovered: bool
    command_available: bool
    observed_at: float | None = None
    output: ProcessOutputStatus
    bans: BanEnforcementStatus
    exit: ProcessExitStatus


class GetServerProcessResponse(SuccessResponse):
    server_name: ServerName
    process: ServerProcessStatus
