"""Serializable system API request and response contracts."""

from .common import APIRequest, APIResponse, ServerName, StateVersion, SuccessResponse


class ProcessInfo(APIResponse):
    pid: int
    cpu_percent: float
    memory_mb: float
    uptime: str


class GetServerRunningStatusRequest(APIRequest):
    server_name: ServerName


class GetServerRunningStatusResponse(SuccessResponse, StateVersion):
    is_running: bool


class GetBedrockProcessInfoRequest(APIRequest):
    server_name: ServerName


class GetBedrockProcessInfoResponse(SuccessResponse, StateVersion):
    process_info: ProcessInfo | None
