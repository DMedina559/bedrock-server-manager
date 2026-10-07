"""HTTP-specific responses; operation data contracts live in api.models."""

from typing import Literal

from ...api.models.common import ActionResponse, APIResponse, SuccessResponse
from ...api.models.tasks import TaskAcceptedResponse


class RegistrationResponse(SuccessResponse):
    registration_url: str


class BackupFilesResponse(SuccessResponse):
    backups: list[str] | dict[str, list[str]]


class BaseApiResponse(APIResponse):
    status: Literal["success", "skipped"]
    message: str | None = None


__all__ = [
    "ActionResponse",
    "TaskAcceptedResponse",
    "RegistrationResponse",
    "BackupFilesResponse",
    "BaseApiResponse",
]
