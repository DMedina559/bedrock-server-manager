"""Public background task contracts; execution handles remain in TaskManager."""

from typing import Literal

from pydantic import JsonValue

from .common import APIErrorResponse, APIResponse


class TaskAcceptedResponse(APIResponse):
    status: Literal["accepted"] = "accepted"
    message: str
    task_id: str


class TaskSnapshot(APIResponse):
    id: str
    status: Literal["queued", "running", "completed", "failed", "cancelling", "cancelled"]
    message: str
    result: JsonValue = None
    error: APIErrorResponse | None = None
